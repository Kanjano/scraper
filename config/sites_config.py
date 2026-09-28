"""Site configuration, built from the worldwide store dataset.

Source of truth: ``config/stores.json`` — 120 internationally known musical
instrument shops (Europe / USA / Asia), each with a stable ``id``.

Per-store *scraping* details (platform, search URL, selectors, blocks) live in
``config/store_overrides.json``, which is produced/refreshed by
``scripts/probe_stores.py`` (live platform detection) and may be hand-edited.
Keeping them apart means the dataset stays the user-provided facts and the
overrides stay the machine-verified scraping surface.

Rules respected here: conservative per-domain rate limit, robots.txt, no
login or captcha solving. Edge anti-bot walls are passed where a shop's public
data is reachable without solving a challenge: the shop's own public search API
(Algolia, Doofinder), a Chrome TLS fingerprint (``impersonate``), or a real
Chrome (``stealth``) — see docs/ANTIBOT_PROXY.md. Stores behind interactive
challenges stay flagged, not forced.
"""
import json
from pathlib import Path

_CONFIG_DIR = Path(__file__).resolve().parent
STORES_FILE = _CONFIG_DIR / "stores.json"
OVERRIDES_FILE = _CONFIG_DIR / "store_overrides.json"

# Identifiable, but with the browser token first: several shops reject requests
# whose UA does not start with a recognised browser string (Thomann answers 429).
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0 Safari/537.36 "
    "StrumentiMusicaliScraper/1.0 (+price research; "
    "contact: antonio.web2music@gmail.com)"
)

_HEADERS = {
    "User-Agent": DEFAULT_USER_AGENT,
    "Accept-Language": "en;q=0.9",
}

# Valid dataset enums (kept in sync with the dataset documentation).
AREAS = ("europe", "usa", "asia")
SPECIALTIES = (
    "general",
    "guitars_bass",
    "vintage_boutique_guitars",
    "classical_flamenco_guitars",
    "drums_percussion",
    "synth_studio_pro_audio",
    "pianos_keyboards",
    "bowed_strings",
    "woodwind_brass",
    "traditional_folk",
    "early_music",
    "marketplace_used",
)
TYPES = (
    "store",
    "online_store",
    "marketplace",
    "auction_house",
    "maker_workshop",
    "multi_shop_arcade",
)

# Search-URL templates per detected e-commerce platform. JSON endpoints are
# preferred: structured, stable, and far lighter than rendering product grids.
PLATFORM_SEARCH_URLS = {
    # /search* is Disallow-ed in Shopify's default robots.txt, so we read the
    # public catalogue feed instead and filter locally (see ShopifyScraper).
    "shopify": "{base}/products.json?limit=250",
    "woocommerce": "{base}/wp-json/wc/store/v1/products?search={{query}}&per_page=24",
    "magento": "{base}/catalogsearch/result/?q={{query}}",
    "prestashop": "{base}/module/ambjolisearch/jolisearch?s={{query}}",
}

# Stores with a hand-written scraper or a known-good non-default route.
# ``scraper_type`` values: requests | shopify | woocommerce | playwright | api
MANUAL_OVERRIDES: dict[str, dict] = {
    "thomann": {
        "platform": "custom",
        "scraper_type": "requests",
        # robots.txt disallows /intl/ for generic agents; the /it/ storefront is
        # allowed and prices in EUR.
        "search_url": "https://www.thomann.de/it/search_dir.html?sw={query}",
        "data_quality": "structured",
        # ThomannScraper parses the embedded GA4 JSON, not these CSS selectors.
        "selectors_verified": True,
        "selectors": {
            "product_container": "div.fx-product-list-entry",
            "name": "span.title__name",
            "brand": "span.title__manufacturer",
            "price": "span.product__price-primary",
            "rating": "div.product__rating-stars",
            "url": "a.product__content",
        },
    },
    "reverb": {
        "platform": "api",
        "scraper_type": "api",
        # Official public API (documented); scraping the HTML is unnecessary.
        "search_url": "https://api.reverb.com/api/listings?query={query}",
        "selectors_verified": True,
        "data_quality": "structured",
    },
    "gear4music": {
        # Search sits behind a Cloudflare challenge and the grid is a Doofinder
        # overlay; its public search API answers directly. "en" engine = GBP.
        "platform": "custom",
        "scraper_type": "doofinder",
        "search_url": "https://eu1-search.doofinder.com/6/f205c1c85ffb23926546500d5d186eb5"
                      "/_search?query={query}",
        "doofinder": {"hashid": "f205c1c85ffb23926546500d5d186eb5", "zone": "eu1"},
        "selectors_verified": True,
        "data_quality": "structured",
    },
    "sweetwater": {
        # PerimeterX blocks the site; its search box queries Algolia with a
        # public search-only key shipped in the storefront bundle.
        "platform": "custom",
        "scraper_type": "algolia",
        "search_url": "https://e2o5c5m9ls-dsn.algolia.net/1/indexes/production_products"
                      "?query={query}",
        "algolia": {
            "app_id": "E2O5C5M9LS",
            "api_key": "37e9e24f5094bbccde5826d4a0a2ce55",
            "index": "production_products",
            "fields": {"name": "productName", "brand": "brand", "price": "price.finalPrice",
                       "url": "url", "stock": "attributes.inStock",
                       "original_price": "price.retailPrice", "image": "image.pathAbsolute"},
        },
        "impersonate": True,
        "selectors_verified": True,
        "data_quality": "structured",
    },
    "perfect-circuit": {
        # Magento + Algolia behind Cloudflare. The search key is a secured key
        # with an expiry, so it is read from the homepage on every search.
        "platform": "magento",
        "scraper_type": "algolia",
        "search_url": "https://h0792vl9d5-dsn.algolia.net/1/indexes/"
                      "perfectcircuit_production_default_products?query={query}",
        "algolia": {
            "app_id": "H0792VL9D5",
            "api_key_re": r'"apiKey":"([^"]+)"',
            "index": "perfectcircuit_production_default_products",
            "fields": {"name": "name", "brand": "brand", "price": "price.USD.default",
                       "url": "url", "stock": "stock_qty", "image": "image_url"},
        },
        "impersonate": True,
        "selectors_verified": True,
        "data_quality": "structured",
    },
    "bax-music": {
        # HTTP 406 to non-browser TLS; fine with a Chrome fingerprint.
        "platform": "custom",
        "scraper_type": "requests",
        "search_url": "https://www.bax-shop.nl/producten.html?keyword={query}",
        "impersonate": True,
        "selectors_verified": True,
        "data_quality": "structured",
        "selectors": {
            "product_container": "div.product-container",
            "name": "h3.product-name-heading a",
            "price": "span.voor-prijs",
            "original_price": "span.van-prijs",
            "url": "h3.product-name-heading a",
        },
    },
    "scan-pro-audio": {
        "platform": "custom",
        "scraper_type": "requests",
        "search_url": "https://www.scan.co.uk/search?q={query}",
        "impersonate": True,
        "selectors_verified": True,
        "data_quality": "structured",
        "selectors": {
            "product_container": "li.product",
            "name": "span.description a span",
            "price": "span.price",
            "url": "span.description a",
        },
    },
    "guitar-salon-international": {
        # OpenCart; the display currency follows the visitor's IP, so pin USD.
        "platform": "opencart",
        "scraper_type": "structured",
        "search_url": "https://www.guitarsalon.com/store?mz_fq={query}",
        "impersonate": True,
        "session_setup": {
            "url": "https://www.guitarsalon.com/index.php?route=common/currency/currency",
            "data": {"code": "USD", "redirect": "https://www.guitarsalon.com/"},
        },
        "data_quality": "heuristic",
    },
    "vintage-instruments": {
        # WooCommerce Store API, 403 to non-browser TLS.
        "platform": "woocommerce",
        "scraper_type": "woocommerce",
        "search_url": "https://vintage-instruments.com/?rest_route=/wc/store/v1/products"
                      "&search={query}&per_page=24",
        "impersonate": True,
        "selectors_verified": True,
        "data_quality": "structured",
    },
    "b-and-h-photo-video": {
        # Cloudflare JS challenge: passes in a real (patchright) Chrome.
        "platform": "custom",
        "scraper_type": "playwright",
        "search_url": "https://www.bhphotovideo.com/c/search?q={query}&sts=ma",
        "stealth": True,
        "requires_javascript": True,
        "selectors_verified": True,
        "data_quality": "structured",
        "selectors": {
            "product_container": "[data-selenium=miniProductPage]",
            "name": "[data-selenium=miniProductPageProductName]",
            # ponytail: dollars only — cents sit in a sibling <sup> that
            # get_text(strip=True) would glue on ("$109 00" -> 10900).
            "price": "[data-selenium=uppedDecimalPriceFirst]",
            "url": "a[data-selenium=miniProductPageProductNameLink]",
        },
    },
    "strumenti-musicali-net": {
        # HTTP 428 JS challenge on every page: passes in a real Chrome.
        "platform": "oscommerce",
        "scraper_type": "playwright",
        "search_url": "https://www.strumentimusicali.net/advanced_search_result.php?keywords={query}",
        "stealth": True,
        "requires_javascript": True,
        "selectors_verified": True,
        "data_quality": "structured",
        "selectors": {
            "product_container": "tr.productListing-even, tr.productListing-odd",
            "name": "b.listing_prod_name",
            "price": "span.productSpecialPrice, span.fontSize14.bold",
            "original_price": "s",
            "url": "a.pdlist",
        },
    },
    "ishibashi-music": {
        # ishibashi.co.jp is the corporate/JP site; the English international
        # storefront (the dataset note mentions it) is a Shopify shop that ships
        # abroad, so the catalogue feed is available there.
        "platform": "shopify",
        "scraper_type": "shopify",
        "search_url": "https://intl.ishibashi.co.jp/products.json?limit=250",
        "origin": "https://intl.ishibashi.co.jp",
        "selectors_verified": True,
        "data_quality": "structured",
    },
    "mcneela-music": {
        # BigCommerce storefront: the search results are built client-side, so the
        # static HTML carries no prices.
        "platform": "bigcommerce",
        "scraper_type": "playwright",
        "search_url": "https://mcneelamusic.com/search.php?search_query={query}",
        "requires_javascript": True,
        "data_quality": "heuristic",
    },
    "swee-lee": {
        # sweelee.com is a landing page; the catalogue lives on the per-country
        # Shopify storefronts (SG is the main one, see the dataset note).
        "platform": "shopify",
        "scraper_type": "shopify",
        "search_url": "https://www.sweelee.com.sg/products.json?limit=250",
        "origin": "https://www.sweelee.com.sg",
        "selectors_verified": True,
        "data_quality": "structured",
    },
    "andertons-music-co": {
        "platform": "custom",
        "scraper_type": "playwright",
        "search_url": "https://www.andertons.co.uk/search?q={query}",
        "requires_javascript": True,
        "selectors_verified": True,
        "data_quality": "structured",
        "selectors": {
            "product_container": "article.productCard",
            "name": "h3.productCard__title",
            "brand": "p.productCard__brand",
            "price": "span.productCard__price",
            "url": "a.productCard__title__link",
        },
    },
}


# Hand-checked explanations for stores the probe cannot read. They replace the
# probe's generic message only while no search route is known: if a shop later
# exposes one, the probe re-enables it and the note disappears by itself.
VERIFIED_BLOCKS: dict[str, str] = {
    # Fine-instrument dealers and workshops: catalogues without public prices
    # ("price on request"), exactly as the dataset warns for maker_workshop.
    "j-and-a-beare": "fine-violin dealer: catalogue without public prices (price on request)",
    "ingles-and-hayday": "fine-violin dealer: catalogue without public prices",
    "casa-parramon": "luthier workshop: catalogue without public prices",
    "felipe-conde-conde-hermanos": "luthier workshop: catalogue without public prices",
    "guitarras-conde-hermanos-atocha": "luthier workshop: catalogue without public prices",
    "guitarreria-mariano-conde": "luthier workshop: catalogue without public prices",
    "manuel-contreras": "luthier workshop: catalogue without public prices",
    "rikhi-ram": "workshop shop: search page lists instruments without prices",
    "steinway-hall": "brand showroom site (steinway.com): no price list published",
    "tarisio": "auction house: lots carry estimates and deadlines, not list prices",
    "charleys-guitar-shop": "listings published without prices",
    "gruhn-guitars": "site moved to guitars.com; listings published without prices",
    "lone-star-percussion": "site replaced by an 'Under Construction' placeholder",
    "replay-guitar-exchange": "rebranded to legendsguitars.com; catalogue not machine-readable",
    "parsons-music": "WooCommerce Store API answers with bare product ids, and the "
                     "search page carries no product data",
    "explorers-percussion": "site serves injected SEO-spam pages (Indonesian "
                            "gambling doorways) alongside the shop; no clean route",
    # Shops whose catalogue is not machine-readable from outside.
    "house-of-guitars": "WooCommerce Store API reachable but its catalogue is empty",
    "dales-drum-shop": "WooCommerce Store API requires authentication (HTTP 401)",
    "drum-tec": "Shopware storefront: prices rendered only after a shop session",
    "lays-guitar-shop": "Wix storefront: no catalogue data in the page",
    "ikebe-gakki": "shop subdomain answers HTTP 403 to non-browser clients",
    "kurosawa-gakki": "catalogue pages carry no machine-readable product data",
    "shimamura-music": "catalogue pages carry no machine-readable product data",
    "shimokura-music": "static brochure site, no online catalogue",
    "mansons-guitar-shop": "domain parked (redirects to a 'domain not in use' page)",
    # Anti-bot walls that need an interactive challenge or another exit IP.
    "guitar-center": "Akamai behavioural challenge (press-and-hold) on search; "
                     "needs a residential proxy or unlocker",
    "hawaii-music-supply-the-ukulele-site": "Cloudflare interactive Turnstile challenge; "
                                            "needs a residential proxy or unlocker",
    "full-compass-systems": "Cloudflare interactive Turnstile challenge; "
                            "needs a residential proxy or unlocker",
    "mccabes-guitar-shop": "whole site behind HTTP 401 authentication",
    "nakwon-musical-instrument-arcade": "HTTP 403 to every client from outside its region",
    "music-store-professional": "robots.txt disallows every search route",
    "muziker": "robots.txt disallows the search routes",
    "pro-guitar-shop": "site now redirects to reverb.com (covered by the Reverb API)",
    # Unreachable from outside their region / behind an edge firewall.
    "west-l-a-music": "host does not answer from outside its region",
    "musik-hug": "host does not answer from outside its region",
    "sound-house": "host does not answer from outside its region",
    "kytary-cz": "host does not answer from outside its region",
    "atlanta-pro-percussion": "host does not answer from outside its region",
    "rayburn-musical-instrument-co": "host does not answer from outside its region",
    "cream-city-music": "host does not answer from outside its region",
}


def load_stores() -> list[dict]:
    with STORES_FILE.open(encoding="utf-8") as fh:
        return json.load(fh)


def load_overrides() -> dict[str, dict]:
    if not OVERRIDES_FILE.exists():
        return {}
    with OVERRIDES_FILE.open(encoding="utf-8") as fh:
        return json.load(fh)


def _priority(store: dict) -> int:
    """1 = global majors, 2 = broad catalogues, 3 = niche / tiny catalogues."""
    if store["top"]:
        return 1
    if store["type"] in ("maker_workshop", "auction_house", "multi_shop_arcade"):
        return 3
    if store["specialty"] in ("general", "marketplace_used"):
        return 2
    return 3


def _rate_limit(store: dict) -> dict:
    """Conservative: one request every ~10s per domain (majors slightly faster)."""
    if store["top"]:
        return {"requests_per_minute": 6, "delay_between_requests": 10}
    return {"requests_per_minute": 4, "delay_between_requests": 15}


def build_sites_config() -> dict[str, dict]:
    overrides = load_overrides()
    out: dict[str, dict] = {}
    for store in load_stores():
        sid = store["id"]
        base_url = store["url"].rstrip("/")
        probe_ov = dict(overrides.get(sid, {}))
        manual = MANUAL_OVERRIDES.get(sid, {})
        if manual.get("search_url"):
            # A hand-written route supersedes whatever the probe concluded,
            # including an earlier "disabled" verdict — but not a verdict the
            # manual entry itself states.
            probe_ov.pop("enabled", None)
            probe_ov.pop("blocked_reason", None)
        ov = {**probe_ov, **manual}

        platform = ov.get("platform", "unknown")
        search_url = ov.get("search_url")
        if not search_url and platform in PLATFORM_SEARCH_URLS:
            origin = ov.get("origin") or base_url
            search_url = PLATFORM_SEARCH_URLS[platform].format(base=origin.rstrip("/"))

        scraper_type = ov.get("scraper_type") or (
            platform if platform in ("shopify", "woocommerce") else "requests"
        )

        cfg = {
            # --- dataset fields (facts about the shop) ---
            "id": sid,
            "name": store["name"],
            "url": base_url,
            "area": store["area"],
            "group": store["group"],
            "country": store["country"],
            "us_state": store["us_state"],
            "city": store["city"],
            "specialty": store["specialty"],
            "type": store["type"],
            "top": store["top"],
            "domain": store["domain"],
            "currency": store["local_currency"],
            "note": store["note"],
            # --- scraping surface ---
            "priority": _priority(store),
            "platform": platform,
            "scraper_type": scraper_type,
            "search_url": search_url,
            "searchable": bool(search_url),
            "selectors": ov.get("selectors", {}),
            "selectors_verified": ov.get("selectors_verified", False),
            # "structured" = JSON feed or schema.org markup; "heuristic" = grid
            # detection, which is best-effort and can mis-read odd layouts.
            "data_quality": ov.get("data_quality"),
            "requires_javascript": ov.get("requires_javascript", False),
            "cloudflare_protected": ov.get("cloudflare_protected", False),
            "robots_allows_search": ov.get("robots_allows_search", True),
            "blocked_reason": (
                VERIFIED_BLOCKS.get(sid, ov.get("blocked_reason"))
                if not search_url
                else ov.get("blocked_reason")
            ),
            "enabled": ov.get("enabled", True),
            # Anti-bot handling (see scrapers.base_scraper / playwright_base).
            "impersonate": ov.get("impersonate", False),
            "stealth": ov.get("stealth", False),
            "session_setup": ov.get("session_setup"),
            "algolia": ov.get("algolia"),
            "doofinder": ov.get("doofinder"),
            "timeout": ov.get("timeout", 30),
            "max_retries": ov.get("max_retries", 3),
            "rate_limit": ov.get("rate_limit") or _rate_limit(store),
            "headers": _HEADERS,
        }
        out[sid] = cfg
    return out


SITES_CONFIG: dict[str, dict] = build_sites_config()


def get_enabled_sites(
    priority: int | None = None,
    area: str | None = None,
    searchable_only: bool = False,
) -> dict[str, dict]:
    out = {}
    for key, cfg in SITES_CONFIG.items():
        if not cfg.get("enabled"):
            continue
        if priority is not None and cfg.get("priority") != priority:
            continue
        if area is not None and cfg.get("area") != area:
            continue
        if searchable_only and not cfg.get("searchable"):
            continue
        out[key] = cfg
    return out


def get_searchable_sites(priority: int | None = None) -> dict[str, dict]:
    """Sites we can actually query (known search route, not blocked)."""
    return {
        k: c
        for k, c in get_enabled_sites(priority=priority, searchable_only=True).items()
        if not c.get("blocked_reason") and c.get("robots_allows_search", True)
    }
