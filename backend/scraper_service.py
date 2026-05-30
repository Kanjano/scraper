"""
Servizio centrale per il coordinamento dello scraping parallelo,
il filtering/ranking dei risultati e i calcoli correlati.
"""

import os
import time
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError

from cache_manager import cleanup_cache, cleanup_on_error
from search_normalizer import normalize_query, fuzzy_match_score, get_query_tokens

from scraper_centrochitarre import cerca_centrochitarre
from scraper_tomassone import cerca_tomassone
from scraper_musik_produktiv import cerca_musik_produktiv
from scraper_thomann import cerca_thomann
from scraper_andertons import cerca_andertons
from scraper_gear4music import cerca_gear4music
from scraper_strumentimusicali import search_strumentimusicali as cerca_strumentimusicali

logger = logging.getLogger("scraper_service")

# ---------------------------------------------------------------------------
# Selenium serialization
# ---------------------------------------------------------------------------
# Su macOS, anche con --user-data-dir univoco, due istanze di
# undetected_chromedriver concorrenti possono entrare in conflitto
# (singleton di Chrome / patcher UC), causando "no such window: target window
# already closed" su uno dei due driver. Serializziamo i 3 scraper Selenium
# tramite un lock condiviso. Gli scraper basati su requests continuano a
# girare in parallelo dentro il ThreadPoolExecutor.
_SELENIUM_LOCK = threading.Lock()
SELENIUM_SCRAPER_KEYS: set = set()  # tutti gli scraper ora HTTP-based

ALL_SCRAPERS = {
    "thomann":           ("Thomann",            cerca_thomann),
    "musik_produktiv":   ("Musik Produktiv",     cerca_musik_produktiv),
    "gear4music":        ("Gear4music",          cerca_gear4music),
    "andertons":         ("Andertons",           cerca_andertons),
    "centrochitarre":    ("Centro Chitarre",     cerca_centrochitarre),
    "tomassone":         ("Tomassone",           cerca_tomassone),
    "strumentimusicali": ("StrumentiMusicali.net", cerca_strumentimusicali),
}

_NAME_MAP = {k: v[0] for k, v in ALL_SCRAPERS.items()}

DEFAULT_MAX_WORKERS  = int(os.environ.get("MAX_WORKERS", 8))
DEFAULT_TIMEOUT_SEC  = int(os.environ.get("SCRAPER_TIMEOUT", 90))
STRICT_MIN_RESULTS   = 5


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _site_active(selected: list, key: str) -> bool:
    if not selected:
        return True
    display = _NAME_MAP.get(key, "")
    return key in selected or display in selected


def _invoke_scraper(key: str, func, query: str):
    """Wrapper che acquisisce _SELENIUM_LOCK per gli scraper Selenium e
    chiama direttamente la funzione per quelli requests-based.
    Garantisce il rilascio del lock anche in caso di eccezione."""
    if key in SELENIUM_SCRAPER_KEYS:
        acquired_at = time.time()
        with _SELENIUM_LOCK:
            wait_s = time.time() - acquired_at
            if wait_s > 0.1:
                logger.info("%s: ha atteso %.2fs il _SELENIUM_LOCK", key, wait_s)
            return func(query)
    return func(query)


def _safe_run(key: str, name: str, func, query: str) -> tuple:
    """Esegue un singolo scraper. Nessun cleanup_cache durante il run parallelo
    per evitare race condition tra driver concorrenti.

    Per gli scraper Selenium (Thomann, Andertons, Gear4music) acquisisce
    `_SELENIUM_LOCK` per serializzarne l'esecuzione: due istanze concorrenti di
    undetected_chromedriver tendono a collidere su macOS. Il retry usa lo
    stesso lock.

    Returns:
        tuple (items: list, error: str | None).
        Quando error è None lo scraper è andato a buon fine (anche con 0 oggetti).
        Quando error è valorizzato l'esecuzione è fallita su entrambi i tentativi.
    """
    logger.info("Avvio scraper: %s", name)
    start = time.time()
    try:
        result = _invoke_scraper(key, func, query)
        if not isinstance(result, list):
            result = []
        for r in result:
            if isinstance(r, dict) and "sito" not in r:
                r["sito"] = name
        logger.info("%s: %d risultati in %.2fs", name, len(result), time.time() - start)
        return result, None
    except Exception as exc:
        err_msg = str(exc)
        logger.warning("%s: errore dopo %.2fs — %s", name, time.time() - start, err_msg[:200])
        try:
            time.sleep(1.0)
            result = _invoke_scraper(key, func, query)
            if not isinstance(result, list):
                result = []
            for r in result:
                if isinstance(r, dict) and "sito" not in r:
                    r["sito"] = name
            logger.info("%s: retry ok — %d risultati", name, len(result))
            return result, None
        except Exception as exc2:
            err2 = str(exc2)
            logger.error("%s: retry fallito — %s", name, err2[:200])
            return [], err2 or err_msg


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_all_scrapers(query: str, sites: list) -> tuple:
    """
    Esegue gli scraper selezionati in parallelo.

    Returns:
        (results: list, stats: dict)
        results — lista piatta di prodotti con chiave 'sito'
        stats   — dizionario {nome_sito: {oggetti, stato, ...}}
    """
    active = {k: v for k, v in ALL_SCRAPERS.items() if _site_active(sites, k)}
    if not active:
        active = dict(ALL_SCRAPERS)

    workers = min(DEFAULT_MAX_WORKERS, len(active))
    logger.info("Avvio scraping su %d siti (workers=%d)", len(active), workers)

    results: list = []
    stats: dict = {}
    t0 = time.time()

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(_safe_run, key, name, func, query): (key, name)
            for key, (name, func) in active.items()
        }
        for future in as_completed(futures):
            key, name = futures[future]
            try:
                outcome = future.result(timeout=DEFAULT_TIMEOUT_SEC)
                # Backward-compat: _safe_run ora restituisce (items, error).
                # Se ci sono callsite che ancora ritornano una lista, accettiamo
                # entrambe le forme.
                if isinstance(outcome, tuple) and len(outcome) == 2:
                    items, err = outcome
                else:
                    items, err = outcome, None
                if not isinstance(items, list):
                    items = []
                results.extend(items)
                if err:
                    stats[name] = {
                        "oggetti": len(items),
                        "stato": "errore",
                        "errore": str(err)[:200],
                    }
                else:
                    stats[name] = {"oggetti": len(items), "stato": "ok"}
            except TimeoutError:
                logger.warning("%s: timeout dopo %ds", name, DEFAULT_TIMEOUT_SEC)
                stats[name] = {"oggetti": 0, "stato": "timeout"}
            except Exception as exc:
                logger.error("%s: eccezione — %s", name, str(exc))
                stats[name] = {"oggetti": 0, "stato": "errore", "errore": str(exc)[:200]}

    stats["_tempo_totale"] = round(time.time() - t0, 2)
    logger.info("Scraping completato: %d risultati in %.2fs", len(results), stats["_tempo_totale"])
    return results, stats


NO_PRICE_SENTINEL = float("inf")


def _parse_price(item: dict) -> float:
    """Restituisce il prezzo corrente in float.

    Preferisce ``prezzo_numerico`` (già parsed dagli scraper). Se assente o
    non valido, fa fallback sul parsing della stringa ``prezzo``. I prodotti
    senza prezzo valido ricevono ``NO_PRICE_SENTINEL`` in modo che finiscano
    in fondo all'ordinamento ascendente.
    """
    try:
        num = item.get("prezzo_numerico")
        if num is not None:
            val = float(num)
            if val > 0:
                return val
    except (TypeError, ValueError):
        pass
    try:
        raw = str(item.get("prezzo", "") or "")
        raw = raw.replace("€", "").replace(" ", "").strip()
        if not raw or raw.upper() == "N/A":
            return NO_PRICE_SENTINEL
        # Format europeo (1.234,56) → 1234.56
        if "," in raw and "." in raw:
            raw = raw.replace(".", "").replace(",", ".")
        elif "," in raw:
            raw = raw.replace(",", ".")
        val = float(raw)
        return val if val > 0 else NO_PRICE_SENTINEL
    except (ValueError, AttributeError):
        return NO_PRICE_SENTINEL


def _filter_strict(items: list, query: str) -> list:
    # Usa get_query_tokens (che rimuove stopwords italiane come "a", "di",
    # "il", ...) per evitare che query come "chitarra a sei corde" filtrino
    # via tutti i risultati per via del token "a".
    tokens = get_query_tokens(query)
    if not tokens:
        # Fallback: se la query è tutta stopwords/parole brevi, usa lo split
        # naive — meglio dei zero risultati.
        tokens = [t.lower() for t in query.split() if t]

    import re as _re
    # Forma "compatta" di ciascun token: solo alfanumerici (es. "p-125" → "p125").
    tokens_compact = [_re.sub(r"\W+", "", t) for t in tokens]

    out = []
    for item in items:
        try:
            raw_name = str(item.get("nome") or item.get("titolo") or item.get("name") or "")
            name = raw_name.lower()
            # Versione compatta del nome: rimuove tutti i separatori
            # (spazi, trattini, slash) così "Yamaha P-125" matcha il token
            # "p125" e viceversa.
            name_compact = _re.sub(r"\W+", "", name)
            ok = True
            for tok, tok_c in zip(tokens, tokens_compact):
                if tok in name:
                    continue
                if tok_c and tok_c in name_compact:
                    continue
                ok = False
                break
            if ok:
                out.append(item)
        except Exception:
            continue
    return out


def filter_and_rank_results(results: list, query: str) -> tuple:
    """
    Filtra e ordina i risultati.

    Returns:
        (ranked_results: list, search_mode: str)
        search_mode è "strict" o "fuzzy"
    """
    if not results:
        return [], "strict"

    norm_q = normalize_query(query)

    strict = _filter_strict(results, norm_q)
    if len(strict) >= STRICT_MIN_RESULTS:
        pool = strict
        mode = "strict"
    else:
        pool = results
        mode = "fuzzy"

    # Calcola relevance_score per ogni item
    for item in pool:
        name = str(item.get("nome") or item.get("titolo") or item.get("name") or "")
        item["relevance_score"] = round(fuzzy_match_score(name, norm_q) * 100)
        # Memorizza il prezzo parsed per debug/frontend e per evitare di
        # ricalcolarlo durante l'ordinamento.
        item["_sort_price"] = _parse_price(item)

    # Ordinamento primario per prezzo crescente (offerte/sconti già riflessi
    # in `prezzo_numerico`). Relevance score come tiebreaker per parità di
    # prezzo. I prodotti senza prezzo valido finiscono in coda grazie a
    # NO_PRICE_SENTINEL.
    ranked = sorted(
        pool,
        key=lambda x: (
            x.get("_sort_price", NO_PRICE_SENTINEL),
            -x.get("relevance_score", 0),
            str(x.get("nome") or x.get("titolo") or "").lower(),
        ),
    )
    # Pulizia: non esponiamo il campo interno al client.
    for item in ranked:
        item.pop("_sort_price", None)
    return ranked, mode


def calculate_discounts(results: list) -> list:
    """Aggiunge sconto_percentuale, risparmio e has_offer a ogni item.

    has_offer è True quando esiste un prezzo originale strettamente maggiore
    del prezzo corrente — utile al frontend per evidenziare le offerte senza
    dover riconfrontare i campi.
    """
    for item in results:
        try:
            curr = float(item.get("prezzo_numerico") or 0)
            orig = float(item.get("prezzo_originale_numerico") or 0)
            if orig > curr > 0:
                item["sconto_percentuale"] = round(((orig - curr) / orig) * 100)
                item["risparmio"] = round(orig - curr, 2)
                item["has_offer"] = True
            else:
                item["sconto_percentuale"] = 0
                item["risparmio"] = 0
                item["has_offer"] = False
        except Exception:
            item["sconto_percentuale"] = 0
            item["risparmio"] = 0
            item["has_offer"] = False
    return results


def apply_referral_links(results: list, referral_manager) -> list:
    """Sostituisce i link con i corrispondenti referral link."""
    for item in results:
        if "link" in item:
            item["link"] = referral_manager.get_referral_link(item["link"])
    return results


def get_top_discounts(results: list, n: int = 10) -> list:
    """Restituisce i primi n prodotti per sconto percentuale."""
    return sorted(
        [r for r in results if r.get("sconto_percentuale", 0) > 0],
        key=lambda x: x["sconto_percentuale"],
        reverse=True,
    )[:n]
