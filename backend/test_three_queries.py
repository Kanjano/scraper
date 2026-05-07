"""Test scrape pipeline for 3 target queries.
Captures: per-site counts, ranked top-10, search_mode, time, matched-field analysis.
"""
import json
import time
from collections import Counter

from scraper_service import run_all_scrapers, filter_and_rank_results, calculate_discounts
from search_normalizer import normalize_query, get_query_tokens

QUERIES = ["fender mustang", "gibson les paul", "friedman"]

report = []
for q in QUERIES:
    print(f"\n{'='*70}\nQUERY: {q!r}\n{'='*70}")
    norm = normalize_query(q)
    tokens = [t.lower() for t in norm.split() if t]
    print(f"normalized: {norm!r}  tokens: {tokens}")

    t0 = time.time()
    raw_results, stats = run_all_scrapers(norm, [])
    scrape_t = round(time.time() - t0, 2)

    raw_results = calculate_discounts(raw_results)
    t1 = time.time()
    ranked, mode = filter_and_rank_results(raw_results, norm)
    rank_t = round(time.time() - t1, 3)

    site_counts = Counter(r.get("sito") for r in raw_results)
    ranked_site_counts = Counter(r.get("sito") for r in ranked)

    # Match-field analysis on ranked top-50
    field_hits = Counter()
    sample_top = []
    for it in ranked[:50]:
        name = str(it.get("nome") or it.get("titolo") or it.get("name") or "")
        nname = normalize_query(name)
        all_in = all(tok in nname for tok in tokens)
        any_in = any(tok in nname for tok in tokens)
        field_hits["all_tokens_in_nome"] += int(all_in)
        field_hits["any_token_in_nome"] += int(any_in)
        field_hits["no_token_in_nome"] += int(not any_in)
    top10 = []
    for it in ranked[:10]:
        top10.append({
            "nome": str(it.get("nome") or it.get("titolo") or it.get("name") or "")[:120],
            "sito": it.get("sito"),
            "prezzo": it.get("prezzo"),
            "relevance_score": it.get("relevance_score"),
        })

    print(f"raw scrape -> {len(raw_results)} items in {scrape_t}s | per-site: {dict(site_counts)}")
    print(f"ranked     -> {len(ranked)} items, mode={mode}, post-rank in {rank_t}s")
    print(f"match-fields top50: {dict(field_hits)}")
    print("TOP 10:")
    for i, it in enumerate(top10, 1):
        print(f"  {i:2}. [{it['relevance_score']:>3}] {it['sito']:<22} | {it['prezzo']!s:<12} | {it['nome']}")

    report.append({
        "query": q,
        "normalized": norm,
        "tokens": tokens,
        "raw_total": len(raw_results),
        "ranked_total": len(ranked),
        "search_mode": mode,
        "scrape_seconds": scrape_t,
        "rank_seconds": rank_t,
        "per_site_raw": dict(site_counts),
        "per_site_ranked": dict(ranked_site_counts),
        "match_fields_top50": dict(field_hits),
        "top10": top10,
        "stats": stats,
    })

with open("test_three_queries_report.json", "w") as f:
    json.dump(report, f, indent=2, ensure_ascii=False)
print("\nSaved -> test_three_queries_report.json")
