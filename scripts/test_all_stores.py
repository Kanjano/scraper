"""Functional test of every store in the dataset, through the real scrapers.

For each store the matching scraper is instantiated from ``config`` and asked
for products with queries suited to that shop's specialty (a drum shop is asked
for a snare, a violin dealer for a violin). A store passes when either

  * it is configured as usable and returns at least one valid offer
    (name + price > 0), or
  * it is configured as not usable and says why (blocked by anti-bot,
    unreachable, robots.txt, no machine-readable catalogue).

Results go to ``data/store_test_report.json`` and are summarised on stdout.
``tests/test_live_stores.py`` then asserts on that report, so pytest stays
offline and deterministic.

Usage:  python -m scripts.test_all_stores [--only id1,id2] [--workers 6]
"""
import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.sites_config import SITES_CONFIG  # noqa: E402
from scrapers.sites import get_scraper  # noqa: E402

REPORT_FILE = Path(__file__).resolve().parents[1] / "data" / "store_test_report.json"

# Queries per specialty: tried in order until one returns offers.
QUERIES = {
    "general": ["fender", "yamaha", "guitar", "case"],
    "guitars_bass": ["fender", "gibson", "guitar", "strings"],
    "vintage_boutique_guitars": ["fender", "gibson", "guitar", "amp"],
    "classical_flamenco_guitars": ["guitar", "guitarra", "flamenco", "cuerdas"],
    "drums_percussion": ["snare", "cymbal", "drum", "stick"],
    "synth_studio_pro_audio": ["moog", "synth", "microphone", "audio"],
    "pianos_keyboards": ["piano", "yamaha", "keyboard", "stand"],
    "bowed_strings": ["violin", "cello", "bow", "rosin"],
    "woodwind_brass": ["sax", "flute", "trumpet", "clarinet", "reed"],
    "traditional_folk": ["ukulele", "whistle", "sitar", "harmonium", "tabla", "bodhran"],
    "early_music": ["recorder", "lute", "harpsichord", "viol"],
    "marketplace_used": ["fender", "gibson", "guitar"],
}


def _valid(offer: dict) -> bool:
    price = offer.get("price")
    return bool(offer.get("name")) and isinstance(price, (int, float)) and price > 0


def test_store(site_key: str, limit: int = 5) -> dict:
    cfg = SITES_CONFIG[site_key]
    usable = bool(cfg["enabled"] and cfg["searchable"])
    out = {
        "site_key": site_key,
        "name": cfg["name"],
        "area": cfg["area"],
        "priority": cfg["priority"],
        "platform": cfg["platform"],
        "scraper_type": cfg["scraper_type"],
        "data_quality": cfg.get("data_quality"),
        "expected": "offers" if usable else "documented_skip",
        "blocked_reason": cfg.get("blocked_reason"),
        "queries_tried": [],
        "offers_found": 0,
        "sample": [],
        "elapsed_s": None,
        "result": None,
        "error": None,
    }
    if not usable:
        out["result"] = "skipped" if cfg.get("blocked_reason") else "misconfigured"
        return out

    started = time.monotonic()
    try:
        with get_scraper(site_key) as scraper:
            for query in QUERIES.get(cfg["specialty"], QUERIES["general"]):
                out["queries_tried"].append(query)
                offers = [o for o in scraper.search(query, limit=limit) if _valid(o)]
                if offers:
                    out["offers_found"] = len(offers)
                    out["sample"] = [
                        {
                            "name": o["name"],
                            "price": o["price"],
                            "currency": o.get("currency"),
                            "price_eur": o.get("price_eur_equivalent"),
                            "url": o.get("url"),
                        }
                        for o in offers[:3]
                    ]
                    break
    except Exception as exc:  # noqa: BLE001
        out["error"] = f"{type(exc).__name__}: {exc}"[:200]
    out["elapsed_s"] = round(time.monotonic() - started, 1)
    out["result"] = "passed" if out["offers_found"] else "failed"
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="comma-separated store ids")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--limit", type=int, default=5)
    args = ap.parse_args()

    keys = list(SITES_CONFIG)
    if args.only:
        wanted = {s.strip() for s in args.only.split(",")}
        keys = [k for k in keys if k in wanted]

    results: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(test_store, k, args.limit): k for k in keys}
        for i, fut in enumerate(as_completed(futures), 1):
            key = futures[fut]
            try:
                res = fut.result()
            except Exception as exc:  # noqa: BLE001
                res = {"site_key": key, "result": "failed", "error": str(exc)[:200]}
            results[key] = res
            sample = res.get("sample") or []
            first = f"{sample[0]['name'][:38]} {sample[0]['price']}" if sample else ""
            print(
                f"[{i:3}/{len(keys)}] {res.get('result','?'):9} {key:45} "
                f"n={res.get('offers_found', 0):3} {first}",
                flush=True,
            )

    report = {}
    if REPORT_FILE.exists() and args.only:
        report = json.loads(REPORT_FILE.read_text(encoding="utf-8")).get("stores", {})
    report.update(results)
    counts: dict[str, int] = {}
    for res in report.values():
        counts[res.get("result", "?")] = counts.get(res.get("result", "?"), 0) + 1
    payload = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "totals": {"stores": len(report), **counts},
        "stores": report,
    }
    REPORT_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\nsummary:", json.dumps(payload["totals"], indent=2))
    return 0 if not counts.get("failed") and not counts.get("misconfigured") else 1


if __name__ == "__main__":
    raise SystemExit(main())
