# Architecture

## Overview

The system is a layered Python application. A FastAPI process exposes the REST
API and, on startup, launches an APScheduler background scheduler. Search
requests fan out to multiple site scrapers in parallel, results are normalized to
EUR and aggregated, and the pricing engine derives a suggested price.

```
            ┌──────────────────────────────────────────────┐
 client ───▶│  FastAPI (api/)                               │
            │   routes: search · pricing · analytics · admin│
            └───────┬───────────────────────┬──────────────┘
                    │                        │
          ┌─────────▼─────────┐    ┌─────────▼──────────┐
          │ ScraperOrchestrator│    │  PricingEngine /   │
          │ (scheduler/)       │    │  MarketAnalyzer    │
          │ parallel fan-out   │    │  (pricing/)        │
          └─────────┬──────────┘    └─────────┬──────────┘
                    │                          │
        ┌───────────▼────────────┐             │
        │ scrapers/sites/*        │             │
        │ Base→Generic→{Thomann,  │             │
        │ Reverb, Playwright,...}  │             │
        └───────────┬────────────┘             │
                    │                          │
   utils: rate_limiter · proxy_manager · currency_converter · logger
                    │                          │
            ┌───────▼──────────────────────────▼───────┐
            │ SQLAlchemy models  ◀──▶  SQLite / Postgres│
            └───────────────────────────────────────────┘

 APScheduler (scheduler/jobs.py): periodic scrape by priority + health checks
```

## Layers and responsibilities

### `config/`
- `settings.py` — `Settings` (pydantic-settings) loaded from `.env`; `settings`
  singleton + `get_settings()`.
- `database.py` — SQLAlchemy `engine`, `SessionLocal`, declarative `Base`,
  `init_db()`, `get_db()` FastAPI dependency.
- `stores.json` — **the dataset**: 120 internationally known shops (Europe 37,
  USA 63, Asia 20) with a stable `id` each.
- `store_overrides.json` — the scraping surface per store (platform, search route,
  scraper type, data quality, block reason), written by `scripts/probe_stores.py`.
- `sites_config.py` — merges the two into `SITES_CONFIG`, adds defaults
  (identifiable UA, per-domain rate limit, priority tier) and `MANUAL_OVERRIDES`
  for hand-written scrapers. Selectors: `get_enabled_sites()`,
  `get_searchable_sites()`. See [CONFIGURATION](CONFIGURATION.md).

### `models/`
SQLAlchemy 2.0 typed models: `Site`, `Instrument`, `PriceHistory`,
`SuggestedPrice`. See [DATA_MODEL](DATA_MODEL.md).

### `scrapers/`
- `base_scraper.py` — `BaseScraper(ABC)`: session, rate limiting, proxy hook,
  retry-with-backoff, validation/normalization, currency conversion.
- `parsers.py` — locale-aware `parse_price` (EU, US and `4.270 ₺` groupings).
- `structured.py` — schema.org extraction (JSON-LD `Product`/`ItemList`, microdata):
  one parser for every shop that publishes product data for search engines.
- `grid.py` — selector-free product-grid detection for shops that publish none:
  finds the repeated block holding a link, a title and a price.
- `validator.py` — `is_valid` / `normalize` (adds `price_eur_equivalent`).
- `sites/` — concrete scrapers + the registry (`get_scraper`). See
  [SCRAPERS](SCRAPERS.md).

### `pricing/`
- `pricing_engine.py` — `PricingEngine.calculate_suggested_price`.
- `market_analyzer.py` — `MarketAnalyzer` (category overview, price trend).

### `scheduler/`
- `orchestrator.py` — `ScraperOrchestrator`: `ThreadPoolExecutor` fan-out across
  sites, aggregation, EUR ranking.
- `jobs.py` — APScheduler job definitions + `build_scheduler()`.

### `api/`
- `main.py` — app factory, lifespan (DB init + scheduler start/stop), router
  registration.
- `routes/` — `search` (incl. the SSE stream), `pricing`, `analytics`, `admin`,
  `contact` (mail form), `favicons` (shop icons from our origin).
- `schemas.py` — Pydantic request/response models.
- `i18n.py` — page language from the visitor's country (CDN header or offline
  GeoIP) and `Accept-Language`.
- `web/` — the INSTRINDER page: template, translations, static CSS/JS/fonts.
  See [FRONTEND](FRONTEND.md).

### `utils/`
`logger` (JSON), `rate_limiter` (per-site min-interval), `currency_converter`
(live rates + static fallback), `proxy_manager` (round-robin pool).

### `cache/`, `monitoring/`
In-memory TTL cache (also holds Shopify catalogue feeds); reachability checker
over all 120 stores + optional Prometheus metrics.

### `scripts/`
- `probe_stores.py` — one-off discovery: robots.txt, reachability, platform
  detection, search-route discovery (including reading the shop's own search
  form), then validation with the runtime parsers. Writes the overrides and
  `data/store_probe.json`.
- `test_all_stores.py` — functional test of all 120 stores through the real
  scrapers, with queries matched to each shop's specialty. Writes
  `data/store_test_report.json`, which `tests/test_live_stores.py` asserts on.

## Request flow — `GET /search?query=...` (and `/search/stream`)

1. `api/routes/search.py` calls `ScraperOrchestrator.search_all_sites`.
2. The query is translated to English locally when needed
   (`scrapers/query_translation.py`); both versions are searched.
3. Orchestrator submits one task per *searchable* store to a thread pool
   (optionally filtered by `priority` tier or `area`); stores with no usable
   route are skipped, not retried blindly.
4. Each task builds its scraper via `get_scraper(site_key)` and runs `search()`.
5. Each scraper rate-limits, fetches (requests / Chrome TLS / hosted search API
   / Playwright), parses (price, pre-discount price, image), validates, and
   normalizes to EUR (`price_eur_equivalent`, `discount_pct`).
6. As each shop answers, `on_event` reports it with its relevant offers — the
   stream endpoint turns these into Server-Sent Events; a `cancel` event stops
   shops not started yet.
7. Orchestrator aggregates: relevance filter, dedupe, accessory flags,
   relevance score, items-then-price ranking, lowest price + market average
   from items only. See [SEARCH](SEARCH.md).
8. Response serialized via `SearchResponse` (or sent as the `done` event).

## Search page flow

Browser → `GET /` (template in the visitor's language) → `app.js` opens
`GET /search/stream` → renders phases, shop icons (`GET /favicon/{key}`) and
offers as they arrive → final ranked list, deals column, client-side sorting.
Contact form → `POST /contact` → SMTP.

## Concurrency

- Cross-site parallelism: `ThreadPoolExecutor` (default 5 workers). I/O-bound
  scraping suits threads.
- Per-site politeness: `RateLimiter` enforces a minimum interval (thread-safe).
- Playwright runs synchronously per call inside its worker thread.
