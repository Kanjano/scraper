# Scrapers

The dataset is 120 shops on a dozen different e-commerce platforms, so the
scraper never hard-codes per-shop CSS. It picks, per store, the most structured
route that shop actually offers — decided once by `scripts/probe_stores.py` and
recorded in `config/store_overrides.json`.

## Route tiers (best first)

| Tier | `scraper_type` | Source of data | Used for |
|------|----------------|----------------|----------|
| 1 | `api` | Official API | Reverb (`api.reverb.com`, public, anonymous) |
| 2 | `shopify` | `/products.json` catalogue feed | every Shopify shop |
| 3 | `woocommerce` | `/wp-json/wc/store/v1/products` Store API | every WooCommerce shop |
| 4 | `requests` | Shop-specific parser | Thomann (embedded GA4 JSON) |
| 5 | `structured` | schema.org JSON-LD / microdata on the search page | Magento, PrestaShop, custom shops |
| 5b | `structured` | repeated-grid detection (`scrapers/grid.py`) | shops with no schema.org data |
| 6 | `playwright` | the same parsers over a Chromium-rendered page | client-side rendered grids |

Tiers 1–4 return canonical shop data (`data_quality: "structured"`). Tier 5b is
a heuristic: it reads the page the way a human does, and is flagged
`data_quality: "heuristic"` so downstream code can treat it as lower confidence.

## Class hierarchy

```
BaseScraper (ABC)                      scrapers/base_scraper.py
├── GenericScraper                     scrapers/sites/generic_scraper.py   (CSS selectors)
│   ├── ThomannScraper                 scrapers/sites/thomann_scraper.py
│   ├── StructuredScraper              scrapers/sites/structured_scraper.py
│   └── PlaywrightScraper              scrapers/sites/playwright_base.py
├── ShopifyScraper                     scrapers/sites/shopify_scraper.py
├── WooCommerceScraper                 scrapers/sites/woocommerce_scraper.py
└── ReverbScraper                      scrapers/sites/reverb_scraper.py
```

Shared parsers: `scrapers/structured.py` (schema.org) and `scrapers/grid.py`
(grid detection) — both used by the scrapers *and* by the probe, so a route that
probes green also works at runtime.

## `BaseScraper`

- `requests.Session` with the identifiable UA, a per-site `RateLimiter`
  (≥10 s between requests), the shared `proxy_manager`.
- `search(query)` / `get_product_details(url)` — abstract.
- `parse_price` — locale-aware (`1.299,99`, `$1,299.99`, `4.270 ₺`).
- `retry_with_backoff`, `respectful_request`, `finalize` (validate + normalize +
  `price_eur_equivalent`), context-manager support.

## `ShopifyScraper`

Shopify's default `robots.txt` disallows `/search*`, so the predictive-search
endpoint is off limits. `/products.json` is allowed and richer: the scraper pulls
up to 4 pages × 250 products once per site (TTL-cached in `cache/`), then filters
locally by query tokens over title/vendor/type/tags. One request per refresh
instead of one per search, and no theme coupling.

Shopify Markets quotes converted prices per visitor region and `/products.json`
never states which currency it used, so the scraper reads the session currency
from `/cart.js` (cached with the catalogue) instead of assuming the shop's home
currency. Without that, a US shop serving EUR to a European visitor would have
its prices converted a second time.

## `WooCommerceScraper`

Reads the public Store API (`/wp-json/wc/store/v1/products?search=…`), the same
read-only API the storefront blocks use. Prices arrive as integer minor units
plus `currency_minor_unit`, which the scraper converts.

## `ThomannScraper`

Thomann fills prices with JS but ships a GA4 ecommerce payload per product in the
static HTML (`"ecommerceEventItem":{…}`). The scraper extracts that JSON and pairs
it with `a.product__content` hrefs. Route is `/it/search_dir.html?sw=` — `/intl/`
is Disallow-ed in their `robots.txt`.

## `ReverbScraper`

Official API, `Accept-Version: 3.0`; `REVERB_API_KEY` raises rate limits.

## `StructuredScraper`

Fetches the shop's search page and tries, in order: JSON-LD `Product`/`ItemList`
→ microdata → repeated-grid detection → the config's CSS selectors. Covers
Magento, PrestaShop, BigCommerce, Shopware and bespoke storefronts with one class.

## `PlaywrightScraper`

Renders the search page in Chromium (light stealth: no `navigator.webdriver`,
real UA/viewport/locale), then runs the same parser chain. For shops whose grid
is built client-side. It is **not** a challenge solver: a Cloudflare interstitial
is recorded as blocked, never worked around. Requires `playwright install chromium`.

## Registry — `scrapers/sites/__init__.py`

```python
SCRAPER_CLASSES = {"thomann": ThomannScraper, "reverb": ReverbScraper}  # by store id
SCRAPER_TYPES  = {"shopify": ShopifyScraper, "woocommerce": WooCommerceScraper,
                  "structured": StructuredScraper, "playwright": PlaywrightScraper,
                  "requests": GenericScraper}
get_scraper(site_key)  # store id → hand-written class, else by scraper_type
```

## Adding or fixing a store

1. Add the shop to `config/stores.json` (the dataset: facts about the shop).
2. Run `python -m scripts.probe_stores --only <id>` — it finds the platform and
   search route, then writes `config/store_overrides.json`.
3. Verify end to end: `python -m scripts.test_all_stores --only <id>`.
4. Only if the shop needs bespoke logic: add a class in `scrapers/sites/`,
   register it in `SCRAPER_CLASSES`, and pin its route in
   `sites_config.MANUAL_OVERRIDES`.

## Policy

- `robots.txt` is honoured per route (`urllib.robotparser`), including Shopify's
  `/search` ban and Thomann's `/intl/` ban.
- Identifiable user-agent with a contact address; ≥10 s per domain.
- No login, CAPTCHA or anti-bot circumvention. Challenged shops are disabled with
  `blocked_reason` and reported, per the dataset's instructions.
