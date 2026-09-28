"""Coordinates parallel scraping across all configured sites."""
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from statistics import mean

from config.sites_config import SITES_CONFIG, get_searchable_sites
from scrapers import query_translation, relevance
from scrapers.sites import get_scraper
from utils.logger import get_logger

logger = get_logger(__name__)


# ponytail: fixed thresholds. A shop "discounting" nearly everything it returned
# shows a list price, not a sale; its cuts stay visible but are not deals.
_EVERYWHERE_SHARE = 0.8
_EVERYWHERE_MIN = 5


def _flag_list_price_discounts(offers: list[dict]) -> None:
    by_site: dict[str, list[dict]] = {}
    for o in offers:
        by_site.setdefault(o.get("site_key"), []).append(o)
    for items in by_site.values():
        on_sale = sum((o.get("discount_pct") or 0) > 0 for o in items)
        everywhere = len(items) >= _EVERYWHERE_MIN and on_sale / len(items) >= _EVERYWHERE_SHARE
        for o in items:
            o["discount_everywhere"] = everywhere and (o.get("discount_pct") or 0) > 0


class ScraperOrchestrator:
    def __init__(self, max_workers: int = 5):
        self.max_workers = max_workers

    def _search_one(self, site_key: str, queries: str | list[str], limit: int) -> list[dict]:
        """Run each query on one shop (the original, then its English version)."""
        return self._run_site(site_key, queries, limit)[0]

    def _run_site(
        self, site_key: str, queries: str | list[str], limit: int
    ) -> tuple[list[dict], str | None]:
        """(offers, error) for one shop; error is set when the shop failed."""
        cfg = SITES_CONFIG.get(site_key, {})
        if isinstance(queries, str):
            queries = [queries]
        try:
            with get_scraper(site_key) as scraper:
                results = [r for q in queries for r in scraper.search(q, limit=limit)]
                for r in results:
                    r["site"] = scraper.name
                    r["site_key"] = site_key
                    r["area"] = cfg.get("area")
                    r["country"] = cfg.get("country")
                    r["data_quality"] = cfg.get("data_quality", "structured")
                return results, (None if results else scraper.last_error)
        except Exception as exc:  # noqa: BLE001
            logger.error("site %s failed: %s", site_key, exc)
            return [], f"{type(exc).__name__}: {exc}"[:200]

    def search_all_sites(
        self,
        query: str,
        sites: list[str] | None = None,
        limit: int = 20,
        priority: int | None = None,
        area: str | None = None,
        on_event=None,
        cancel=None,
    ) -> dict:
        """Query every searchable store (optionally filtered) in parallel.

        ``on_event(kind, data)`` receives progress as it happens (phases, each
        shop as it answers with its relevant offers); ``cancel`` is a
        ``threading.Event`` that stops shops not started yet.
        """
        emit = on_event or (lambda kind, data: None)
        start = time.monotonic()
        keys = sites or [
            k for k, c in get_searchable_sites(priority=priority).items()
            if area is None or c.get("area") == area
        ]
        emit("phase", {"id": "prepare", "status": "active"})
        # Shops search in their own language: a non-English query also goes out
        # in English, so foreign catalogues can answer it.
        english = query_translation.to_english(query)
        queries = [query] + ([english] if english else [])
        emit("start", {
            "query": query,
            "translated_query": english,
            "sites": [
                {"key": k, "name": SITES_CONFIG[k]["name"], "url": SITES_CONFIG[k]["url"],
                 "area": SITES_CONFIG[k]["area"]}
                for k in keys
            ],
        })
        emit("phase", {"id": "prepare", "status": "done"})
        emit("phase", {"id": "search", "status": "active"})
        all_results: list[dict] = []
        cancelled = False
        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = {pool.submit(self._run_site, k, queries, limit): k for k in keys}
            for done, fut in enumerate(as_completed(futures), 1):
                key = futures[fut]
                results, error = fut.result() if not fut.cancelled() else ([], "cancelled")
                all_results.extend(results)
                if done == 1:
                    emit("phase", {"id": "filter", "status": "active"})
                relevant = self._relevant(results, query, english)
                emit("site", {
                    "key": key,
                    "name": SITES_CONFIG[key]["name"],
                    "status": "error" if error else ("ok" if results else "empty"),
                    "error": error,
                    "offers": len(results),
                    "relevant": [self._offer_out(r) for r in relevant],
                    "done": done,
                    "total": len(keys),
                })
                if cancel is not None and cancel.is_set() and not cancelled:
                    cancelled = True
                    for f in futures:
                        f.cancel()
        emit("phase", {"id": "search", "status": "done"})
        emit("phase", {"id": "filter", "status": "done"})
        emit("phase", {"id": "rank", "status": "active"})
        out = self.aggregate_results(
            query, all_results, time.monotonic() - start, sites_queried=len(keys),
            english=english,
        )
        emit("phase", {"id": "rank", "status": "done"})
        return out

    @staticmethod
    def _relevant(results: list[dict], query: str, english: str | None) -> list[dict]:
        relevant = relevance.filter_relevant(results, query)
        if english:  # offers matching the English version count as well
            ids = {id(r) for r in relevant}
            relevant += [r for r in relevance.filter_relevant(results, english)
                         if id(r) not in ids]
        return relevant

    @staticmethod
    def _offer_out(r: dict) -> dict:
        return {
            "site": r.get("site"),
            "site_key": r.get("site_key"),
            "area": r.get("area"),
            "country": r.get("country"),
            "name": r.get("name"),
            "price": r.get("price"),
            "currency": r.get("currency"),
            "price_eur": r.get("price_eur_equivalent"),
            "rating": r.get("rating"),
            "url": r.get("url"),
            "data_quality": r.get("data_quality"),
            "is_accessory": r.get("is_accessory", False),
            "image": r.get("image"),
            "original_price": r.get("original_price"),
            "original_price_eur": r.get("original_price_eur"),
            "discount_pct": r.get("discount_pct", 0),
            "relevance": r.get("relevance", 0.0),
            "discount_everywhere": r.get("discount_everywhere", False),
        }

    def aggregate_results(
        self, query: str, results: list[dict], elapsed: float, sites_queried: int = 0,
        english: str | None = None,
    ) -> dict:
        terms = relevance.query_terms(query)
        relevant = self._relevant(results, query, english)
        if english:
            terms += relevance.query_terms(english)
        priced, seen = [], set()
        for r in relevant:
            if not r.get("price_eur_equivalent"):
                continue
            key = (r.get("site_key"), r.get("url") or r.get("name"), r.get("price"))
            if key in seen:  # same listing returned twice by a shop
                continue
            seen.add(key)
            priced.append(r)
        relevance.flag_accessories(priced, terms)
        # Ranking by relevance is the client's choice; the score travels with
        # each offer (best fit of the original query or its English version).
        variants = [relevance.query_terms(query)] + ([relevance.query_terms(english)] if english else [])
        for r in priced:
            r["relevance"] = max(relevance.score(r, v) for v in variants)
        _flag_list_price_discounts(priced)
        # What was asked for first, parts/accessories after; cheapest first in each.
        priced.sort(key=lambda r: (r["is_accessory"], r["price_eur_equivalent"]))
        ranked = []
        for i, r in enumerate(priced, 1):
            ranked.append({"rank": i, **self._offer_out(r)})
        # Market figures from the items themselves, not their spare parts.
        main = [r for r in ranked if not r["is_accessory"]] or ranked
        prices = [r["price_eur"] for r in main]
        return {
            "query": query,
            "translated_query": english,
            "sites_queried": sites_queried or len({r.get("site_key") for r in results}),
            "total_results": len(ranked),
            "lowest_price": main[0]["price_eur"] if main else None,
            "lowest_price_site": main[0]["site"] if main else None,
            "market_average": round(mean(prices), 2) if prices else None,
            "results": ranked,
            "search_time_seconds": round(elapsed, 2),
        }
