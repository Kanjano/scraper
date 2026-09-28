"""Site scraper registry — dispatch by the platform detected per store."""
from config.sites_config import SITES_CONFIG
from scrapers.base_scraper import BaseScraper
from scrapers.sites.algolia_scraper import AlgoliaScraper
from scrapers.sites.doofinder_scraper import DoofinderScraper
from scrapers.sites.generic_scraper import GenericScraper
from scrapers.sites.playwright_base import PlaywrightScraper
from scrapers.sites.reverb_scraper import ReverbScraper
from scrapers.sites.shopify_scraper import ShopifyScraper
from scrapers.sites.structured_scraper import StructuredScraper
from scrapers.sites.thomann_scraper import ThomannScraper
from scrapers.sites.woocommerce_scraper import WooCommerceScraper

# Hand-written scrapers, keyed by store id (dataset ids).
SCRAPER_CLASSES: dict[str, type[BaseScraper]] = {
    "thomann": ThomannScraper,
    "reverb": ReverbScraper,
}

# Everything else is chosen by `scraper_type` from the store config.
SCRAPER_TYPES: dict[str, type[BaseScraper]] = {
    "shopify": ShopifyScraper,
    "woocommerce": WooCommerceScraper,
    "structured": StructuredScraper,
    "playwright": PlaywrightScraper,
    "requests": GenericScraper,
    "algolia": AlgoliaScraper,
    "doofinder": DoofinderScraper,
}


def scraper_class_for(site_key: str, cfg: dict) -> type[BaseScraper]:
    if site_key in SCRAPER_CLASSES:
        return SCRAPER_CLASSES[site_key]
    return SCRAPER_TYPES.get(cfg.get("scraper_type", "requests"), StructuredScraper)


def get_scraper(site_key: str) -> BaseScraper:
    cfg = SITES_CONFIG[site_key]
    return scraper_class_for(site_key, cfg)(cfg)
