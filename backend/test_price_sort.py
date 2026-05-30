"""Verifica che i risultati siano ordinati per prezzo crescente.

Esegue una batteria di ricerche su tutti gli scraper attivi e per ognuna
controlla:
  1. La sequenza dei prezzi numerici è non decrescente (lowest-first).
  2. I prodotti senza prezzo valido sono in coda alla lista.
  3. I campi offerta/sconto sono presenti e coerenti.
  4. Tutti i siti rispondono (almeno N siti diversi).

Si ferma solo quando TUTTE le query passano in un'unica esecuzione: in caso
contrario stampa il dettaglio dei mismatch.
"""
from __future__ import annotations

import json
import math
import sys
import time
from collections import Counter

from scraper_service import (
    run_all_scrapers,
    filter_and_rank_results,
    calculate_discounts,
    apply_referral_links,
)
from referral_db_manager import ReferralDBManager

QUERIES = [
    "fender stratocaster",
    "gibson les paul",
    "ibanez rg",
    "yamaha p225",
    "shure sm7b",
    "boss ds-1",
    "marshall jcm800",
    "prs custom 24",
    "fender jaguar",
    "heritage h 150",
]
REQUIRED_SITES_MIN = 3
MAX_ATTEMPTS = 3  # retry l'intera batteria se mismatch transitorio


def _check_query(query: str) -> dict:
    """Esegue scraping + ranking e verifica l'ordine per prezzo."""
    t0 = time.time()
    raw, stats = run_all_scrapers(query, [])
    raw = calculate_discounts(raw)
    try:
        raw = apply_referral_links(raw, ReferralDBManager)
    except Exception:
        # In ambienti di test senza DB referral, ignora.
        pass
    ranked, mode = filter_and_rank_results(raw, query)
    elapsed = round(time.time() - t0, 2)

    site_counts = Counter(r.get("sito") for r in ranked)
    siti_attivi = [s for s, n in site_counts.items() if n > 0]

    # Verifica ordinamento: prezzi numerici non decrescenti.
    prices = []
    for r in ranked:
        try:
            p = float(r.get("prezzo_numerico") or 0)
        except (TypeError, ValueError):
            p = 0.0
        # 0 / mancante → infinito (deve stare in coda).
        prices.append(p if p > 0 else math.inf)

    monotonic_ok = all(prices[i] <= prices[i + 1] for i in range(len(prices) - 1))

    # Trova la prima posizione che rompe l'invariante.
    breach = None
    for i in range(len(prices) - 1):
        if prices[i] > prices[i + 1]:
            breach = {
                "indice": i,
                "prezzo_prima": prices[i] if not math.isinf(prices[i]) else None,
                "prezzo_dopo": prices[i + 1] if not math.isinf(prices[i + 1]) else None,
                "nome_prima": ranked[i].get("nome"),
                "nome_dopo": ranked[i + 1].get("nome"),
            }
            break

    # Verifica campi offerta.
    offer_consistent = all(
        ("sconto_percentuale" in r and "has_offer" in r and "risparmio" in r)
        for r in ranked
    )

    # Riepilogo offerte.
    n_with_offer = sum(1 for r in ranked if r.get("has_offer"))

    siti_ok = len(siti_attivi) >= REQUIRED_SITES_MIN

    return {
        "query": query,
        "tempo_s": elapsed,
        "mode": mode,
        "totale": len(ranked),
        "siti_count": len(siti_attivi),
        "per_sito": dict(site_counts),
        "monotonic_ok": monotonic_ok,
        "offer_consistent": offer_consistent,
        "n_with_offer": n_with_offer,
        "siti_ok": siti_ok,
        "breach": breach,
        "primi_5_prezzi": [
            {"sito": r.get("sito"), "nome": (r.get("nome") or "")[:60], "prezzo": r.get("prezzo_numerico")}
            for r in ranked[:5]
        ],
    }


def _passed(check: dict) -> bool:
    return check["monotonic_ok"] and check["offer_consistent"] and check["siti_ok"]


def main() -> int:
    final_report = []
    for attempt in range(1, MAX_ATTEMPTS + 1):
        print(f"\n{'#' * 72}\n# TENTATIVO {attempt}/{MAX_ATTEMPTS}\n{'#' * 72}")
        results = []
        for q in QUERIES:
            print(f"\n--- {q} ---")
            r = _check_query(q)
            flag = "OK " if _passed(r) else "KO "
            print(f"{flag} totale={r['totale']:>3} siti={r['siti_count']}/7 "
                  f"mode={r['mode']} offerte={r['n_with_offer']} "
                  f"sort_ok={r['monotonic_ok']} t={r['tempo_s']}s")
            if r["breach"]:
                print(f"   BREACH @ idx {r['breach']['indice']}: "
                      f"{r['breach']['prezzo_prima']} > {r['breach']['prezzo_dopo']}")
            results.append(r)

        all_ok = all(_passed(r) for r in results)
        final_report = results
        if all_ok:
            print(f"\n✔ Tutte le {len(QUERIES)} query passano al tentativo {attempt}.")
            break
        else:
            failing = [r["query"] for r in results if not _passed(r)]
            print(f"\n✘ {len(failing)} query fallite: {failing}. Retry...")

    else:  # nessun break → tutti i tentativi falliti
        print("\n⚠ Correlazione non esatta dopo tutti i tentativi.")

    out = "test_price_sort_report.json"
    with open(out, "w") as f:
        json.dump(final_report, f, indent=2, ensure_ascii=False)
    print(f"\nReport salvato in {out}")

    return 0 if all(_passed(r) for r in final_report) else 1


if __name__ == "__main__":
    sys.exit(main())
