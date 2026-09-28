"""Scraper record mapping, without touching the network."""
import json

import pytest

from config.sites_config import SITES_CONFIG
from scrapers.sites.shopify_scraper import ShopifyScraper
from scrapers.sites.structured_scraper import StructuredScraper
from scrapers.sites.woocommerce_scraper import WooCommerceScraper


class FakeResponse:
    def __init__(self, payload=None, text=""):
        self._payload = payload
        self.text = text

    def json(self):
        if self._payload is None:
            raise ValueError("not json")
        return self._payload


def _cfg(site_key: str, **over) -> dict:
    cfg = dict(SITES_CONFIG[site_key])
    cfg.update(over)
    return cfg


SHOPIFY_FEED = {
    "products": [
        {
            "id": 111,
            "title": "Fender Player Stratocaster",
            "handle": "fender-player-strat",
            "vendor": "Fender",
            "product_type": "Electric Guitars",
            "tags": ["guitar"],
            "variants": [
                {"price": "849.00", "available": False},
                {"price": "799.00", "available": True},
            ],
        },
        {
            "id": 222,
            "title": "Ludwig Snare Drum",
            "handle": "ludwig-snare",
            "vendor": "Ludwig",
            "variants": [{"price": "649.95", "available": True}],
        },
    ]
}

WOO_PAYLOAD = [
    {
        "id": 7,
        "name": "Sitar Professional",
        "permalink": "https://example.com/p/sitar",
        "prices": {"price": "4500000", "currency_code": "INR", "currency_minor_unit": 2},
        "categories": [{"name": "Sitar"}],
        "is_in_stock": True,
        "average_rating": "4.5",
        "review_count": 12,
    },
    {"id": 8, "name": "No price", "prices": {}, "categories": [3, 4]},
    99,  # some installs answer with bare ids
]


@pytest.fixture
def shopify(monkeypatch):
    from cache.cache_manager import cache

    cache.clear()
    scraper = ShopifyScraper(
        _cfg("memphis-drum-shop",
             search_url="https://memphisdrumshop.com/products.json?limit=250",
             scraper_type="shopify", platform="shopify")
    )
    def fake_get(url, **kw):
        if url.endswith("/cart.js"):
            return FakeResponse({"currency": "EUR", "items": []})
        return FakeResponse(SHOPIFY_FEED if "page=1" in url else {"products": []})

    monkeypatch.setattr(scraper, "respectful_request", fake_get)
    return scraper


def test_shopify_filters_locally_and_takes_the_lowest_variant(shopify):
    offers = shopify.search("fender stratocaster")
    assert len(offers) == 1
    offer = offers[0]
    assert offer["name"] == "Fender Player Stratocaster"
    assert offer["brand"] == "Fender"
    assert offer["price"] == 799.0  # cheapest variant, not the first
    assert offer["stock"] == 1
    assert offer["url"] == "https://memphisdrumshop.com/products/fender-player-strat"
    assert offer["price_eur_equivalent"] > 0


def test_shopify_query_with_no_match_returns_nothing(shopify):
    assert shopify.search("harpsichord") == []


def test_shopify_uses_the_presentment_currency(shopify):
    # Shopify Markets quotes a US shop in EUR to a European visitor, and
    # /products.json never says so — /cart.js does.
    offer = shopify.search("ludwig snare")[0]
    assert offer["currency"] == "EUR"  # not the configured USD
    assert offer["price"] == 649.95
    assert offer["price_eur_equivalent"] == 649.95


def test_woocommerce_minor_units_and_odd_payloads(monkeypatch):
    scraper = WooCommerceScraper(
        _cfg("haribhau-vishwanath",
             search_url="https://www.haribhau.com/wp-json/wc/store/v1/products?search={query}",
             scraper_type="woocommerce")
    )
    monkeypatch.setattr(scraper, "respectful_request", lambda url, **kw: FakeResponse(WOO_PAYLOAD))
    offers = scraper.search("sitar")
    assert len(offers) == 1  # priceless product and the bare id are dropped
    offer = offers[0]
    assert offer["price"] == 45000.0  # 4500000 minor units, exponent 2
    assert offer["currency"] == "INR"
    assert offer["category"] == "Sitar"
    assert offer["rating"] == 4.5


def test_structured_scraper_uses_the_parser_chain(monkeypatch):
    html = """
    <html><body><script type="application/ld+json">
    {"@type":"Product","name":"Yamaha YAS-280 Alto Sax","url":"/p/yas280",
     "offers":{"@type":"Offer","price":"1199.00","priceCurrency":"USD"}}
    </script></body></html>
    """
    scraper = StructuredScraper(
        _cfg("saxquest", search_url="https://www.saxquest.com/search?q={query}")
    )
    monkeypatch.setattr(scraper, "respectful_request", lambda url, **kw: FakeResponse(text=html))
    offers = scraper.search("sax")
    assert len(offers) == 1
    assert offers[0]["name"] == "Yamaha YAS-280 Alto Sax"
    assert offers[0]["price"] == 1199.0
    assert offers[0]["url"].startswith("https://www.saxquest.com/")


def test_json_is_valid_in_both_config_files():
    for path in ("config/stores.json", "config/store_overrides.json"):
        with open(path, encoding="utf-8") as fh:
            assert json.load(fh)


class _FakeHttp(FakeResponse):
    def raise_for_status(self):
        return None


def test_algolia_maps_nested_hit_fields(monkeypatch):
    from scrapers.sites.algolia_scraper import AlgoliaScraper

    hit = {"objectID": "Sub37", "productName": "Subsequent 37", "brand": "Moog",
           "url": "/store/detail/Sub37", "price": {"finalPrice": 1899},
           "attributes": {"inStock": 35}}
    s = AlgoliaScraper(_cfg("sweetwater", rate_limit={"requests_per_minute": 1000}))
    monkeypatch.setattr(s.session, "post", lambda *a, **k: _FakeHttp({"hits": [hit]}))
    [rec] = s.search("moog")
    assert rec["name"] == "Subsequent 37" and rec["price"] == 1899.0
    assert rec["url"] == "https://www.sweetwater.com/store/detail/Sub37"
    assert rec["stock"] == 35 and rec["currency"] == "USD"


def test_doofinder_maps_results(monkeypatch):
    from scrapers.sites.doofinder_scraper import DoofinderScraper

    res = {"id": "1", "title": "Fender Redondo Mini", "brand": "Fender",
           "link": "/Guitar/Fender-Redondo/79E1", "best_price": 149.0, "price": 169.0}
    s = DoofinderScraper(_cfg("gear4music", rate_limit={"requests_per_minute": 1000}))
    monkeypatch.setattr(s, "respectful_request", lambda *a, **k: FakeResponse({"results": [res]}))
    [rec] = s.search("fender")
    assert rec["price"] == 149.0 and rec["currency"] == "GBP"
    assert rec["url"] == "https://www.gear4music.com/Guitar/Fender-Redondo/79E1"
