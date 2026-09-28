"""Scraper for shops whose search page publishes schema.org product data.

Covers Magento / PrestaShop / BigCommerce / custom platforms with a single
parser (see ``scrapers.structured``). Falls back to the config's CSS selectors
via GenericScraper when no structured data is present.
"""
from urllib.parse import quote_plus, urljoin

from scrapers.sites.generic_scraper import GenericScraper
from scrapers.structured import extract_any, extract_products


class StructuredScraper(GenericScraper):
    def search(self, query: str, limit: int = 20, **kwargs) -> list[dict]:
        form = self.config.get("search_post")  # {"field": "{query}"} for POST search forms
        if form:
            url = self.config["search_url"]
            extra = {"data": {k: v.format(query=query) for k, v in form.items()}}
        else:
            url, extra = self.config["search_url"].format(query=quote_plus(query)), {}
        try:
            resp = self.retry_with_backoff(self.respectful_request, url, **extra)
        except Exception as exc:  # noqa: BLE001
            self.logger.error("search failed: %s", exc)
            return []

        records, quality = extract_any(resp.text, limit=limit)
        if quality and quality != self.config.get("data_quality"):
            self.logger.info("read %d products via %s", len(records), quality)
        if not records and self.config.get("selectors"):
            return super().search(query, limit=limit, **kwargs)

        out = []
        for rec in records[:limit]:
            rec["currency"] = rec.get("currency") or self.currency
            for key in ("url", "image"):
                if rec.get(key):
                    rec[key] = urljoin(self.config["url"], rec[key])
            out.append(rec)
        return self.finalize(out)

    def get_product_details(self, product_url: str) -> dict:
        try:
            resp = self.retry_with_backoff(self.respectful_request, product_url)
        except Exception as exc:  # noqa: BLE001
            self.logger.error("details failed: %s", exc)
            return {}
        records = extract_products(resp.text) or extract_any(resp.text, limit=1)[0]
        if not records:
            return super().get_product_details(product_url)
        rec = records[0]
        rec["currency"] = rec.get("currency") or self.currency
        rec["url"] = product_url
        return rec
