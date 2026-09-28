# Strumenti Musicali Scraper

Price aggregator over **120 internationally known musical-instrument shops**
(Europe 37 · USA 63 · Asia 20). FastAPI + SQLAlchemy + APScheduler: it searches
every shop it can read, normalises prices to EUR, and computes a competitive
suggested price.

**80 of the 120 shops return live offers today**; the other 40 are disabled with a
recorded reason (interactive anti-bot challenge, robots.txt, no public prices, or
an unreachable host). See [STATUS](docs/STATUS.md).

📖 **Full documentation in [`docs/`](docs/README.md)** —
[Architecture](docs/ARCHITECTURE.md) ·
[Configuration](docs/CONFIGURATION.md) ·
[Data model](docs/DATA_MODEL.md) ·
[Scrapers](docs/SCRAPERS.md) ·
[API](docs/API.md) ·
[Pricing](docs/PRICING.md) ·
[Anti-bot & proxy](docs/ANTIBOT_PROXY.md) ·
[Status](docs/STATUS.md)

## Stack

- Python 3.11+
- FastAPI + Uvicorn (API)
- SQLAlchemy 2.0 + Alembic (ORM / migrations), SQLite dev / PostgreSQL prod
- requests + BeautifulSoup (static scraping); Playwright/Chromium for JS-only shops
- curl_cffi (Chrome TLS fingerprint) and patchright + Google Chrome for shops behind
  edge anti-bot walls — see [Anti-bot](docs/ANTIBOT_PROXY.md)
- APScheduler (periodic scraping by site priority)
- Prometheus client (optional metrics)

## Layout

```
config/        stores.json (the 120-shop dataset), store_overrides.json (probed
               routes), sites_config.py (merge + defaults), settings, DB engine
scrapers/      base_scraper (ABC), parsers, structured.py (schema.org),
               inline_json.py (embedded catalogues), grid.py (grid detection),
               validator, sites/ (per-platform scrapers + registry)
scripts/       probe_stores.py (route discovery), test_all_stores.py (live test)
models/        SQLAlchemy models: Site, Instrument, PriceHistory, SuggestedPrice
pricing/       PricingEngine (suggested price), MarketAnalyzer
scheduler/     ScraperOrchestrator (parallel search), APScheduler jobs
api/           FastAPI app, routes (search, pricing, analytics, admin), schemas
utils/         logger, rate_limiter, currency_converter
cache/         in-memory TTL cache
monitoring/    health_checker, Prometheus metrics
tests/         pytest suite
```

## Quick start

```bash
cd strumenti-musicali-scraper
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python main.py            # serves http://localhost:8000  (docs at /docs)
```

## Web page (INSTRINDER)

`GET /` from a browser serves **INSTRINDER**, a Google-style search page: one bar
on the home, a results list with area tabs, light/dark theme. Files:
`api/web/index.html` (template), `api/web/static/app.css` (design tokens),
`api/web/static/app.js` (no dependencies), self-hosted Google Sans Flex (OFL).

- Searches stream live from `GET /search/stream` (Server-Sent Events: `phase`,
  `start`, `site`, `done`, `error`): the page shows real phases, each shop as it
  answers and relevant offers as they arrive; the list is sorted by price at the
  end. Closing the connection (Stop / Esc) cancels shops not started yet.
- `?q=…&area=…&priority=1` is shareable; back/forward work.
- Shop icons come from `GET /favicon/{site_key}` (fetched once server-side,
  cached in `data/cache/favicons/`, letter badge when missing), so visitors
  never contact the shops' domains.
- Demo mode for development, localhost only: `/?demo=fast|slow|empty|error|partial`
  replays fake events to try every loading state without scraping.

### Languages

`GET /` from a browser serves the page in the visitor's language (18 languages:
en, zh, zh-Hant, hi, es, fr, ar, bn, pt, ru, ur, id, de, ja, it, ko, tr, sw; Arabic
and Urdu right-to-left). The country comes from the CDN header (`CF-IPCountry`,
CloudFront, Vercel, App Engine) or, without one, from the client IP via the
offline DB-IP Lite database; multilingual countries use the browser's
`Accept-Language` to choose. `?lang=xx` overrides and is remembered in a cookie.
API clients (no `text/html` in `Accept`) still get JSON. Details in `api/i18n.py`.

GeoIP database (optional, monthly, CC BY 4.0 — attribution is in the page footer):

```bash
curl -s https://download.db-ip.com/free/dbip-country-lite-$(date +%Y-%m).mmdb.gz \
  | gunzip > data/dbip-country-lite.mmdb
```

Adding a language: add a block to `api/web/translations.json` with the same keys.

## Search relevance

Shops' own search engines are loose, so every offer is checked again in
`scrapers/relevance.py`: each word of the query must appear in the product name
or brand — literally, as a prefix ("strat" ↔ "Stratocaster"), or with the same
meaning in another language ("violino" ↔ "violin", "chitarra" ↔ "Gitarre"). The
last check uses a local multilingual embedding model
(`paraphrase-multilingual-MiniLM-L12-v2`, ~240 MB, ONNX via fastembed): it is
downloaded once into `data/models/` and then runs offline, with no external AI
service. `SEMANTIC_MODEL=` (empty) turns it off.

Non-English queries are also sent in English (`scrapers/query_translation.py`),
because shops search their own catalogue in their own language: "chitarra
elettrica fender" goes out as-is and as "guitar electric fender". Translation is
local — a curated gear glossary (`scrapers/data/gear_glossary.json`, 49 concepts
in ~13 languages) first, then the embedding model for unknown words, only when
near-certain; brands and models pass through unchanged. The API returns it as
`translated_query`.

Parts and accessories are ranked last and left out of the lowest price and the
average: products made "for" the searched item ("rosin for violin", "pece per
violino"), and names whose main segment is a part word (pickup, case, strings,
sheet music…) priced well below the typical match.

Grid-parsed prices skip instalment offers ("$392/month", financing blocks) and
re-join prices split across elements ("$" "4,699" ".99").

## Key endpoints

- `GET  /search?query=stratocaster` — search every readable shop, ranked by EUR
  price; filter with `priority=1..3`, `area=europe|usa|asia`, `sites=id1,id2`
- `GET  /stores` — the dataset with each shop's scraping state
- `GET  /admin/coverage` — how many shops are readable, and why the rest are not
- `POST /pricing` — body: list of `{site, price_eur, reviews, stock}` → suggested price
- `GET  /market-analysis` — category counts + average prices
- `GET  /price-history/{instrument_id}?days=30` — price trend
- `GET  /admin/sites-status` — per-shop config + scrape status
- `POST /admin/force-scrape?priority=1` — scrape a priority tier now
- `POST /admin/sync-sites` — upsert the dataset into the `sites` table

## Pricing logic

Anchor = lowest non-outlier EUR price across sites. Discount = 7% base,
+3% if a bestseller (>500 reviews), +2% if high stock (>20), capped at
`MARGIN_MAX_PERCENT` (default 15%). Suggested = anchor × (1 − discount).

## Adding a shop

1. Add it to `config/stores.json` (facts only: name, area, city, specialty, url…).
2. `python -m scripts.probe_stores --only <id>` — finds the platform and the search
   route (it even reads the shop's own search form), writes `store_overrides.json`.
3. `python -m scripts.test_all_stores --only <id>` — end-to-end check.
4. Only for bespoke logic: a class in `scrapers/sites/` + an entry in
   `SCRAPER_CLASSES`, and pin its route in `sites_config.MANUAL_OVERRIDES`.

## Tests

```bash
pytest                            # offline: dataset, config, parsers, scrapers,
                                  # plus assertions on the last live report
python -m scripts.test_all_stores # live: all 120 shops through the real scrapers
```

## Scraping strategies (per shop)

The route is decided per shop by `scripts/probe_stores.py`, preferring the most
structured source available — never per-shop CSS if something better exists:

1. **Official API** — Reverb (`api.reverb.com`, public; `REVERB_API_KEY` raises limits).
2. **Platform feeds** — Shopify `/products.json` (33 shops), WooCommerce Store API (6).
3. **Shop-specific parser** — Thomann's embedded GA4 JSON.
4. **schema.org** — JSON-LD / microdata on the search page.
5. **Embedded catalogue JSON** — what Wix/Next.js/Nuxt storefronts ship for their own JS.
6. **Grid detection** — `scrapers/grid.py` finds the repeated priced block; flagged
   `data_quality: "heuristic"`.
7. **Chromium rendering** — `PlaywrightScraper` for client-side-only grids
   (`playwright install chromium`). Not a challenge solver.

### Verified live (2026-09-27)

80/120 shops return offers. Highlights: Thomann, Reverb, Sweetwater, B&H,
Gear4music, Perfect Circuit, Bax Music, Andertons, Chicago Music Exchange, Carter
Vintage, Elderly, Swee Lee, Ishibashi, Tom Lee, Bajaao, Zuhal Müzik. Still
blocked: Guitar Center, The Ukulele Site, Full Compass (interactive challenges);
Music Store, Muziker (robots.txt). Full table and per-shop reasons:
[STATUS](docs/STATUS.md).

### Anti-bot

Edge walls are passed by the shop's public search API (Algolia/Doofinder), a
Chrome TLS fingerprint (`impersonate: true`, curl_cffi) or a real Chrome
(`stealth: true`, patchright) — see [Anti-bot](docs/ANTIBOT_PROXY.md).
Interactive challenges (Turnstile, Akamai press-and-hold) need residential-proxy
rotation or a commercial unlocker API. Proxy support is wired in (`utils/proxy_manager.py`): set
`USE_PROXY=True` and `PROXY_LIST` (round-robin, auth supported) — applied to both
the `requests` scrapers and `PlaywrightScraper` (Chromium proxy). Avoid
captcha-solver services — clear ToS violation. Public price data is generally
defensible; evading explicit blocks is grayer. Respect robots.txt and terms.

## Note on data quality

Every offer carries `data_quality`: `structured` (API, platform feed or
schema.org), `inline_json` (the shop's own embedded catalogue) or `heuristic`
(grid read from the layout — right most of the time, not always). Shops move and
re-brand, so re-run `python -m scripts.probe_stores` periodically; it is
idempotent and only rewrites `config/store_overrides.json`.
