"""
Servizio centrale per il coordinamento dello scraping parallelo,
il filtering/ranking dei risultati e i calcoli correlati.
"""

import os
import time
import logging
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

ALL_SCRAPERS = {
    "thomann":           ("Thomann",            cerca_thomann),
    "musik_produktiv":   ("Musik Produktiv",     cerca_musik_produktiv),
    "gear4music":        ("Gear4music",          cerca_gear4music),
    "andertons":         ("Andertons",           cerca_andertons),
    "centrochitarre":    ("Centro Chitarre",     cerca_centrochitarre),
    "tomassone":         ("Tomassone",           cerca_tomassone),
    "strumentimusicali": ("Strumenti Musicali",  cerca_strumentimusicali),
}

_NAME_MAP = {k: v[0] for k, v in ALL_SCRAPERS.items()}

DEFAULT_MAX_WORKERS  = int(os.environ.get("MAX_WORKERS", 3))
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


def _safe_run(key: str, name: str, func, query: str) -> list:
    """Esegue un singolo scraper. Nessun cleanup_cache durante il run parallelo
    per evitare race condition tra driver concorrenti."""
    logger.info("Avvio scraper: %s", name)
    start = time.time()
    try:
        result = func(query)
        if not isinstance(result, list):
            result = []
        for r in result:
            if isinstance(r, dict) and "sito" not in r:
                r["sito"] = name
        logger.info("%s: %d risultati in %.2fs", name, len(result), time.time() - start)
        return result
    except Exception as exc:
        err_msg = str(exc)
        logger.warning("%s: errore dopo %.2fs — %s", name, time.time() - start, err_msg[:200])
        try:
            time.sleep(1.0)
            result = func(query)
            if not isinstance(result, list):
                result = []
            for r in result:
                if isinstance(r, dict) and "sito" not in r:
                    r["sito"] = name
            logger.info("%s: retry ok — %d risultati", name, len(result))
            return result
        except Exception as exc2:
            logger.error("%s: retry fallito — %s", name, str(exc2)[:200])
        return []


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
                items = future.result(timeout=DEFAULT_TIMEOUT_SEC)
                results.extend(items)
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


def _parse_price(item: dict) -> float:
    try:
        raw = str(item.get("prezzo", "") or item.get("prezzo_numerico", 0))
        raw = raw.replace("€", "").replace(".", "").replace(",", ".").strip()
        return float(raw) if raw else 999_999.0
    except (ValueError, AttributeError):
        return 999_999.0


def _filter_strict(items: list, query: str) -> list:
    tokens = [t.lower() for t in query.split() if t]
    out = []
    for item in items:
        try:
            name = str(item.get("nome") or item.get("titolo") or item.get("name") or "").lower()
            if all(tok in name for tok in tokens):
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

    ranked = sorted(
        pool,
        key=lambda x: (-x.get("relevance_score", 0), _parse_price(x)),
    )
    return ranked, mode


def calculate_discounts(results: list) -> list:
    """Aggiunge sconto_percentuale a ogni item."""
    for item in results:
        try:
            curr = float(item.get("prezzo_numerico") or 0)
            orig = float(item.get("prezzo_originale_numerico") or 0)
            if orig > curr > 0:
                item["sconto_percentuale"] = round(((orig - curr) / orig) * 100)
            else:
                item["sconto_percentuale"] = 0
        except Exception:
            item["sconto_percentuale"] = 0
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
