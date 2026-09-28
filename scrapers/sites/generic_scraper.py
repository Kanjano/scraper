"""Config-driven scraper that works for any site described by CSS selectors.

Reads `search_url` and `selectors` from the site config. Good enough for static
(server-rendered) sites; JS-heavy sites need a Selenium subclass.
"""
from urllib.parse import quote_plus, urljoin

from bs4 import BeautifulSoup

from scrapers.base_scraper import BaseScraper
from scrapers.parsers import first_attr, img_src, text_or_none


class GenericScraper(BaseScraper):
    def _soup(self, url: str) -> BeautifulSoup:
        resp = self.retry_with_backoff(self.respectful_request, url)
        return BeautifulSoup(resp.text, "lxml")

    def search(self, query: str, limit: int = 20, **kwargs) -> list[dict]:
        sel = self.config["selectors"]
        url = self.config["search_url"].format(query=quote_plus(query))
        try:
            soup = self._soup(url)
        except Exception as exc:  # noqa: BLE001
            self.logger.error("search failed: %s", exc)
            return []

        records: list[dict] = []
        for node in soup.select(sel["product_container"])[:limit]:
            name = text_or_none(node.select_one(sel["name"]))
            price = self.parse_price(text_or_none(node.select_one(sel["price"])) or "")
            link_node = node.select_one(sel.get("url", "a"))
            href = first_attr(link_node, "href")
            rating = self.parse_price(text_or_none(node.select_one(sel.get("rating", ""))) or "") \
                if sel.get("rating") else None
            was = self.parse_price(text_or_none(node.select_one(sel["original_price"])) or "") \
                if sel.get("original_price") else None
            image = img_src(node.select_one(sel.get("image", "img")))
            records.append(
                {
                    "name": name,
                    "price": price,
                    "original_price": was,
                    "image": urljoin(self.config["url"], image) if image else None,
                    "currency": self.currency,
                    "rating": rating,
                    "url": urljoin(self.config["url"], href) if href else None,
                    "external_id": href,
                }
            )
        return self.finalize(records)

    def get_product_details(self, product_url: str) -> dict:
        try:
            soup = self._soup(product_url)
        except Exception as exc:  # noqa: BLE001
            self.logger.error("details failed: %s", exc)
            return {}
        sel = self.config["selectors"]
        return {
            "name": text_or_none(soup.select_one(sel["name"])),
            "price": self.parse_price(text_or_none(soup.select_one(sel["price"])) or ""),
            "currency": self.currency,
            "url": product_url,
        }
