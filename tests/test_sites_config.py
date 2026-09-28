"""The scraping configuration derived from the dataset + probe overrides."""
from config.sites_config import (
    MANUAL_OVERRIDES,
    SITES_CONFIG,
    get_enabled_sites,
    get_searchable_sites,
    load_overrides,
    load_stores,
)
from scrapers.sites import SCRAPER_TYPES, scraper_class_for

KNOWN_TYPES = set(SCRAPER_TYPES) | {"api"}


def test_every_store_configured():
    assert set(SITES_CONFIG) == {s["id"] for s in load_stores()}


def test_config_shape():
    for key, cfg in SITES_CONFIG.items():
        assert cfg["id"] == key
        assert cfg["priority"] in (1, 2, 3)
        assert cfg["scraper_type"] in KNOWN_TYPES, f"{key}: {cfg['scraper_type']}"
        assert cfg["currency"] and len(cfg["currency"]) == 3
        assert cfg["rate_limit"]["delay_between_requests"] >= 10, "stay polite"
        assert cfg["headers"]["User-Agent"]
        assert not cfg["url"].endswith("/")
        if cfg["searchable"]:
            assert cfg["search_url"]
        else:
            assert cfg["search_url"] is None


def test_search_urls_are_templated_or_catalogue_feeds():
    for key, cfg in SITES_CONFIG.items():
        url = cfg["search_url"]
        if not url:
            continue
        # Either the query is substituted, or it is a whole-catalogue feed the
        # scraper filters locally (Shopify /products.json).
        assert "{query}" in url or cfg["scraper_type"] == "shopify", key


def test_disabled_stores_say_why():
    for key, cfg in SITES_CONFIG.items():
        if not cfg["enabled"]:
            assert cfg["blocked_reason"], f"{key} disabled without a reason"


def test_searchable_is_subset_of_enabled():
    searchable = set(get_searchable_sites())
    assert searchable <= set(get_enabled_sites())
    for key in searchable:
        assert SITES_CONFIG[key]["search_url"]


def test_scraper_class_resolves_for_every_store():
    for key, cfg in SITES_CONFIG.items():
        cls = scraper_class_for(key, cfg)
        assert hasattr(cls, "search")


def test_overrides_reference_known_stores():
    known = set(SITES_CONFIG)
    assert set(load_overrides()) <= known
    assert set(MANUAL_OVERRIDES) <= known


def test_priority_tiers_reflect_the_dataset():
    for cfg in SITES_CONFIG.values():
        if cfg["top"]:
            assert cfg["priority"] == 1
        elif cfg["type"] in ("maker_workshop", "auction_house", "multi_shop_arcade"):
            assert cfg["priority"] == 3
