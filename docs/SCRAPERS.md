# Scrapers

The dataset is 120 shops on a dozen different e-commerce platforms, so the
scraper never hard-codes per-shop CSS. It picks, per store, the most structured
route that shop actually offers — decided once by `scripts/probe_stores.py` and
recorded in `config/store_overrides.json`.

## Route tiers (best first)

| Tier | `scraper_type` | Source of data | Used for |
|------|----------------|----------------|----------|
| 1 | `api` | Official API | Reverb (`api.reverb.com`, public, anonymous) |
| 1b | `algolia` · `doofinder` · `constructor` | the public search API the shop's own search box calls | Sweetwater, Perfect Circuit (Algolia) · Gear4music (Doofinder) · Andertons (Constructor.io) |
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
├── ReverbScraper                      scrapers/sites/reverb_scraper.py
├── AlgoliaScraper                     scrapers/sites/algolia_scraper.py
├── DoofinderScraper                   scrapers/sites/doofinder_scraper.py
└── ConstructorScraper                 scrapers/sites/constructor_scraper.py
```

## What a scraper returns

Every scraper returns records through `BaseScraper.finalize` (validate +
normalize). Fields: `name`, `brand`, `price`, `currency`, `url`, `external_id`,
`rating`, `stock`, and — when the source has them — `image` (product photo URL)
and `original_price` (the price before a discount, same currency).
`validator.normalize` adds `price_eur_equivalent`, and `discount_pct` +
`original_price_eur` when the pre-sale price is a plausible 1–90 % above the
price. See [SEARCH](SEARCH.md#5-prices-discounts-and-deals) for each source.

Shared parsers: `scrapers/structured.py` (schema.org) and `scrapers/grid.py`
(grid detection) — both used by the scrapers *and* by the probe, so a route that
probes green also works at runtime.

## `BaseScraper`

- `requests.Session` with the identifiable UA, a per-site `RateLimiter`
  (≥10 s between requests), the shared `proxy_manager`. With `impersonate: true`
  the session is a `curl_cffi` one with Chrome's TLS/HTTP2 fingerprint; with
  `session_setup` it POSTs once before searching (e.g. Guitar Salon's currency).
- `last_error` — set when retries are exhausted, so the orchestrator can report
  a failed shop apart from a shop with no matching offers.
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

Catalogues larger than that window are completed through the shop's
collections: `/collections.json` is listed once (cached), and when the query
names a collection — any run of its words as a handle, longest first
("fender-custom-shop", "fender") — up to two collection feeds
(`/collections/<handle>/products.json`) are read and merged. Both endpoints are
allowed by Shopify's default `robots.txt`.

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

## `AlgoliaScraper` · `DoofinderScraper` · `ConstructorScraper`

Many storefronts' search boxes call a hosted search service with a public,
search-only key shipped in the page. Querying that service directly returns
structured results (name, price, list price, image, URL) without touching the
shop's bot-protected pages. Settings live in the store override:

- `algolia`: `app_id`, `index`, `api_key` or `api_key_re` (regex that reads a
  rotating key from the homepage), `fields` (dotted paths: `name`, `price`,
  `original_price`, `url`, `image`, `brand`, `stock`).
- `doofinder`: `hashid` (search engine for the shop's language/currency), `zone`.
- `constructor`: `key`, `fields` (`price`, `sale_price`, `url`, `image`, `brand`).

## `StructuredScraper`

Fetches the shop's search page (or POSTs its search form when the override has
`search_post`) and tries, in order: JSON-LD `Product`/`ItemList` → microdata →
repeated-grid detection → the config's CSS selectors. Grid detection takes the
product photo from the card or, when the priced block leaves it out, from the
nearest wrapper holding that card only. Covers
Magento, PrestaShop, BigCommerce, Shopware and bespoke storefronts with one class.

## `GenericScraper` (CSS selectors)

Selector keys: `product_container`, `name`, `price`, optional `original_price`,
`url` (`:scope` when the card itself is the link), `image` (default: first
`img`), `brand`. Names are read with spaces between elements
(`<strong>Fender</strong> Custom Shop` → "Fender Custom Shop"); prices are read
joined ("£29." + "99" → "£29.99").

## `PlaywrightScraper`

Renders the search page in Chromium, then applies the selectors or the same
parser chain. For shops whose grid is built client-side. With `stealth: true`
it drives the installed Google Chrome through patchright (no automation leaks,
"Headless" removed from the UA), which clears non-interactive challenges
(Cloudflare JS check, PerimeterX, HTTP 428). It is **not** a captcha solver.
Requires `playwright install chromium`, and Google Chrome for `stealth`.

## Registry — `scrapers/sites/__init__.py`

```python
SCRAPER_CLASSES = {"thomann": ThomannScraper, "reverb": ReverbScraper}  # by store id
SCRAPER_TYPES  = {"shopify": ShopifyScraper, "woocommerce": WooCommerceScraper,
                  "structured": StructuredScraper, "playwright": PlaywrightScraper,
                  "requests": GenericScraper, "algolia": AlgoliaScraper,
                  "doofinder": DoofinderScraper, "constructor": ConstructorScraper}
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

### Checking that a route really searches

A page can parse as a perfect product grid and still ignore the query (a
homepage, a "popular items" block). The 2026-09-28 audit found seven shops on a
`/?s=…&post_type=product` fallback that did exactly that. Before trusting a
route, search two unrelated queries (e.g. "gibson" and "yamaha"): the results
must differ and match the words. When the shop's search is built in the
browser, open it in a real browser, type a query into its own search box, and
use the resulting URL — or the JSON API it calls (Algolia, Doofinder,
Constructor, GraphQL).

## Policy

- `robots.txt` is honoured per route (`urllib.robotparser`), including Shopify's
  `/search` ban and Thomann's `/intl/` ban.
- Identifiable user-agent with a contact address; ≥10 s per domain.
- No login and no captcha solving. Edge anti-bot walls are passed only where the
  public data is reachable without solving a challenge (public search APIs,
  Chrome fingerprint, real Chrome); shops behind interactive challenges (Guitar
  Center, Musician's Friend, Full Compass, The Ukulele Site) are disabled with a
  `blocked_reason`. See [ANTIBOT_PROXY](ANTIBOT_PROXY.md).
