"""
Verifica veridicità: per ogni risultato di una ricerca campione, recupera la pagina
del prodotto via HTTP e controlla che il prezzo dichiarato sia presente nell'HTML.
"""
import re
import json
import time
import requests
from collections import defaultdict
from scraper_service import run_all_scrapers

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36")

QUERIES = ["fender jaguar", "gibson les paul", "ibanez rg"]
SAMPLES_PER_SITE = 2  # campioni per sito per query


def _format_price_variants(prezzo: float):
    """Genera varianti formattate del prezzo per matchare HTML eterogenei."""
    intero = int(prezzo)
    decimali = round((prezzo - intero) * 100)
    variants = set()
    # 1399.00, 1399,00, 1.399,00, 1,399.00, 1399
    variants.add(f"{intero}")
    variants.add(f"{intero}.{decimali:02d}")
    variants.add(f"{intero},{decimali:02d}")
    if intero >= 1000:
        thousands_dot = f"{intero:,}".replace(",", ".")
        thousands_comma = f"{intero:,}"
        variants.add(thousands_dot)
        variants.add(thousands_comma)
        variants.add(f"{thousands_dot},{decimali:02d}")
        variants.add(f"{thousands_comma}.{decimali:02d}")
    return variants


def verify_item(item):
    """Restituisce dict con esito verifica."""
    link = item.get("link", "")
    prezzo = item.get("prezzo_numerico", 0)
    nome = item.get("nome", "")
    sito = item.get("sito", "")

    res = {
        "sito": sito,
        "nome": nome[:80],
        "link": link,
        "prezzo_dichiarato": prezzo,
        "http_status": None,
        "prezzo_match": False,
        "nome_match": False,
        "errore": None,
    }

    if not link or not prezzo:
        res["errore"] = "link o prezzo mancanti"
        return res

    try:
        r = requests.get(link, headers={
            "User-Agent": UA,
            "Accept-Language": "it-IT,it;q=0.9",
        }, timeout=15)
        res["http_status"] = r.status_code
        if r.status_code != 200:
            res["errore"] = f"HTTP {r.status_code}"
            return res

        html = r.text
        # Verifica che almeno 1 token significativo del nome compaia nell'HTML
        tokens = [t for t in re.split(r'[\s\-/]+', nome) if len(t) >= 3]
        nome_hits = sum(1 for t in tokens[:5] if t.lower() in html.lower())
        res["nome_match"] = nome_hits >= 2

        # Verifica prezzo: cerca varianti
        for variant in _format_price_variants(prezzo):
            if variant in html:
                res["prezzo_match"] = True
                break

    except Exception as e:
        res["errore"] = str(e)[:120]

    return res


def main():
    sample_items = []
    for q in QUERIES:
        print(f"\n>>> Ricerca: {q}")
        results, _ = run_all_scrapers(q, [])
        # Raggruppa per sito e prendi N campioni
        by_site = defaultdict(list)
        for r in results:
            by_site[r.get("sito", "?")].append(r)
        for sito, items in by_site.items():
            for it in items[:SAMPLES_PER_SITE]:
                sample_items.append(it)

    print(f"\n>>> Campioni totali da verificare: {len(sample_items)}")

    out = []
    for i, item in enumerate(sample_items, 1):
        print(f"  [{i}/{len(sample_items)}] {item.get('sito')} — {item.get('nome', '')[:60]}")
        out.append(verify_item(item))
        time.sleep(0.4)

    ok = [x for x in out if x["prezzo_match"] and x["nome_match"]]
    fail = [x for x in out if not (x["prezzo_match"] and x["nome_match"])]
    print(f"\n=== RIEPILOGO VERIDICITÀ ===")
    print(f"Verificati con successo (nome+prezzo presenti): {len(ok)}/{len(out)}")
    by_site_ok = defaultdict(lambda: [0, 0])
    for x in out:
        by_site_ok[x["sito"]][1] += 1
        if x["prezzo_match"] and x["nome_match"]:
            by_site_ok[x["sito"]][0] += 1
    for sito, (k, n) in by_site_ok.items():
        print(f"  {sito:<25} {k}/{n}")

    print("\n--- Campioni falliti ---")
    for f in fail[:10]:
        print(f"  {f['sito']:<22} prezzo_match={f['prezzo_match']} nome_match={f['nome_match']} err={f['errore']}")
        print(f"      {f['link']}")

    with open("test_veracity_report.json", "w") as fp:
        json.dump(out, fp, indent=2, ensure_ascii=False)
    print("\nReport salvato in test_veracity_report.json")


if __name__ == "__main__":
    main()
