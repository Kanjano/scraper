"""Esegue una batteria di ricerche per validare lo scraping multi-sito."""
import json
import time
from collections import Counter
from scraper_service import run_all_scrapers, filter_and_rank_results

QUERIES = [
    "fender jaguar",
    "heritage h 150",
    "gibson les paul",
    "fender stratocaster",
    "ibanez rg",
    "prs custom 24",
    "marshall jcm800",
    "boss ds-1",
    "yamaha p125",
    "shure sm7b",
]

REQUIRED_SITES_MIN = 3  # almeno 3 siti diversi devono restituire risultati

report = []
for q in QUERIES:
    print(f"\n{'='*70}\nQUERY: {q}\n{'='*70}")
    t0 = time.time()
    results, stats = run_all_scrapers(q, [])
    elapsed = round(time.time() - t0, 2)
    site_counts = Counter(r.get("sito") for r in results)
    siti_attivi = [s for s, n in site_counts.items() if n > 0]
    ok = len(siti_attivi) >= REQUIRED_SITES_MIN
    print(f"Siti con risultati: {len(siti_attivi)} -> {dict(site_counts)}")
    print(f"Totale prodotti: {len(results)}  | tempo: {elapsed}s | OK={ok}")
    report.append({
        "query": q,
        "ok": ok,
        "totale": len(results),
        "siti_count": len(siti_attivi),
        "per_sito": dict(site_counts),
        "tempo": elapsed,
    })

print("\n\n" + "=" * 70)
print("RIEPILOGO FINALE")
print("=" * 70)
for r in report:
    flag = "✅" if r["ok"] else "❌"
    print(f"{flag} {r['query']:<25} siti={r['siti_count']}/7  prodotti={r['totale']}  ({r['tempo']}s)")

total_ok = sum(1 for r in report if r["ok"])
print(f"\nQuery valide (>= {REQUIRED_SITES_MIN} siti): {total_ok}/{len(report)}")

with open("test_multi_search_report.json", "w") as f:
    json.dump(report, f, indent=2, ensure_ascii=False)
print("Report salvato in test_multi_search_report.json")
