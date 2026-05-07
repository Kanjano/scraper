"""20-query validation. Pass = ALL 7 sites stato=ok for ALL queries."""
import json
import sys
import time
from collections import Counter

from scraper_service import run_all_scrapers, filter_and_rank_results, calculate_discounts, ALL_SCRAPERS
from search_normalizer import normalize_query

QUERIES = [
    "fender stratocaster",
    "gibson les paul",
    "ibanez rg",
    "prs custom 24",
    "fender telecaster",
    "gibson sg",
    "marshall jcm800",
    "fender mustang",
    "boss ds-1",
    "shure sm58",
    "yamaha p125",
    "vox ac30",
    "roland td-17",
    "korg minilogue",
    "akg c414",
    "behringer x32",
    "focusrite scarlett",
    "electro-harmonix big muff",
    "audio technica at2020",
    "tc electronic hall of fame",
]

ALL_SITES = [name for (name, _func) in ALL_SCRAPERS.values()]
print(f"Sites under test: {ALL_SITES}")
print(f"Queries: {len(QUERIES)}")

report = []
failures = []
t_start = time.time()
for i, q in enumerate(QUERIES, 1):
    print(f"\n[{i}/{len(QUERIES)}] {'='*60}\nQUERY: {q!r}")
    norm = normalize_query(q)
    t0 = time.time()
    raw, stats = run_all_scrapers(norm, [])
    elapsed = round(time.time() - t0, 2)
    raw = calculate_discounts(raw)
    ranked, mode = filter_and_rank_results(raw, norm)
    site_counts = Counter(r.get("sito") for r in raw)

    site_status = {}
    for site_name in ALL_SITES:
        s = stats.get(site_name, {})
        site_status[site_name] = {
            "stato": s.get("stato", "missing"),
            "oggetti": s.get("oggetti", 0),
            "errore": s.get("errore"),
        }

    bad = [(s, info) for s, info in site_status.items() if info["stato"] != "ok"]
    print(f"raw {len(raw)} | ranked {len(ranked)} | mode {mode} | {elapsed}s")
    for site_name, info in site_status.items():
        flag = "OK " if info["stato"] == "ok" else "ERR"
        err = f" ({info['errore']})" if info.get("errore") else ""
        print(f"  {flag} {site_name:<24} oggetti={info['oggetti']:<4}{err}")

    if bad:
        failures.append({"query": q, "bad_sites": [s for s, _ in bad]})

    report.append({
        "query": q,
        "normalized": norm,
        "raw_total": len(raw),
        "ranked_total": len(ranked),
        "search_mode": mode,
        "elapsed": elapsed,
        "per_site": site_status,
    })

total_elapsed = round(time.time() - t_start, 1)
with open("test_twenty_queries_report.json", "w") as f:
    json.dump({"report": report, "failures": failures, "total_seconds": total_elapsed}, f, indent=2, ensure_ascii=False)

print("\n" + "=" * 70)
print("RIEPILOGO")
print("=" * 70)
print(f"Queries: {len(QUERIES)}  | tempo totale: {total_elapsed}s")
print(f"Failures: {len(failures)}")
for f in failures:
    print(f"  {f['query']!r:<35} bad sites: {f['bad_sites']}")

if failures:
    print("\nFAIL: non tutti i siti hanno stato=ok per tutte le query")
    sys.exit(1)
print("\nPASS: tutti i siti stato=ok per tutte le query")
sys.exit(0)
