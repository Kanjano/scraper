# API Reference

FastAPI app (`api/main.py`). Interactive docs at `/docs` (Swagger) and `/redoc`.
On startup the app initializes the database and (if `SCHEDULER_ENABLED`) starts
the APScheduler background scheduler; both are torn down on shutdown via the
lifespan handler.

Base URL: `http://localhost:8000`

## Root

### `GET /`
Service banner.
```json
{ "service": "strumenti-musicali-scraper", "docs": "/docs" }
```

## Search (`api/routes/search.py`)

### `GET /search`
Search every *searchable* store in parallel, ranked by EUR price. Stores without
a usable route (anti-bot, no machine-readable catalogue) are skipped, not retried.

Query params:
- `query` (str, required, min length 1)
- `limit` (int, default 20) — max results per store
- `priority` (1–3, optional) — 1 = global majors, 2 = broad catalogues, 3 = niche
- `area` (`europe` | `usa` | `asia`, optional)
- `sites` (str, optional) — comma-separated store ids, e.g. `thomann,reverb`

Response (`SearchResponse`):
```json
{
  "query": "stratocaster",
  "sites_queried": 74,
  "total_results": 42,
  "lowest_price": 159.0,
  "lowest_price_site": "Thomann",
  "market_average": 612.5,
  "results": [
    {
      "rank": 1,
      "site": "Thomann",
      "site_key": "thomann",
      "area": "europe",
      "country": "DE",
      "name": "Squier Sonic Strat HT Arctic White",
      "price": 159.0,
      "currency": "EUR",
      "price_eur": 159.0,
      "rating": null,
      "url": "https://www.thomann.de/...",
      "data_quality": "structured"
    }
  ],
  "search_time_seconds": 3.21
}
```

`data_quality` says how the number was obtained: `structured` (official API, JSON
feed or schema.org markup), `inline_json` (the shop's own embedded catalogue
JSON), or `heuristic` (product grid read from the page layout — lower confidence).

### `GET /search-all-sites`
Same behavior and shape as `/search` (alias kept from the spec).

### `GET /stores`
The store dataset as configured, with each store's scraping state.

Query params: `area`, `specialty`, `searchable_only` (bool).
```json
{
  "total": 120,
  "stores": [
    { "site_key": "thomann", "name": "Thomann", "area": "europe",
      "group": "Germania", "country": "DE", "city": "Treppendorf (Burgebrach), Baviera",
      "specialty": "general", "type": "store", "top": true,
      "url": "https://www.thomann.de", "currency": "EUR", "platform": "custom",
      "priority": 1, "searchable": true, "enabled": true, "blocked_reason": null }
  ]
}
```

## Pricing (`api/routes/pricing.py`)

### `POST /pricing`
Compute a suggested price from a list of offers (already in EUR).

Request body — list of offers:
```json
[
  { "site": "A", "price_eur": 100, "reviews": 600, "stock": 30 },
  { "site": "B", "price_eur": 120, "reviews": 5,  "stock": 2 }
]
```

Response (`PricingResponse`):
```json
{
  "price_suggested": 88.0,
  "margin_percentage": 12.0,
  "margin_amount": 12.0,
  "lowest_price_site": "A",
  "lowest_price": 100.0,
  "market_average": 110.0,
  "total_sites_analyzed": 2,
  "reasoning": "base discount 7%; +3% bestseller (>500 reviews); ..."
}
```
Returns `400` if no priced offers are supplied. See [PRICING](PRICING.md).

## Analytics (`api/routes/analytics.py`)

### `GET /market-analysis`
Category counts and average EUR prices over stored instruments.
```json
{
  "total_instruments": 0,
  "overall_avg_price_eur": 0,
  "categories": [
    { "category": "guitars", "count": 120, "avg_price_eur": 540.2 }
  ]
}
```

### `GET /price-history/{instrument_id}`
Price trend for one instrument.

Query params: `days` (int, default 30).
```json
{
  "instrument_id": 1,
  "days": 30,
  "trend": "down",
  "points": [ { "date": "2026-05-20T00:00:00", "price_eur": 199.0 } ]
}
```

## Admin (`api/routes/admin.py`)

### `GET /admin/sites-status`
Per-store config + last scrape state (joins `SITES_CONFIG` with the `sites` table).

Query params: `area`, `priority`.
```json
[
  { "site_key": "thomann", "name": "Thomann", "area": "europe", "group": "Germania",
    "country": "DE", "city": "Treppendorf (Burgebrach), Baviera",
    "specialty": "general", "type": "store", "top": true, "platform": "custom",
    "currency": "EUR", "searchable": true, "enabled": true, "priority": 1,
    "data_quality": "structured", "blocked_reason": null,
    "last_scrape": null, "scrape_status": "never", "error_count": 0 }
]
```

### `GET /admin/coverage`
How much of the dataset is actually readable, and why the rest is not.
```json
{
  "stores_total": 120,
  "stores_usable": 74,
  "by_area": { "europe": { "total": 37, "usable": 21 }, "usa": { "total": 63, "usable": 40 },
               "asia": { "total": 20, "usable": 13 } },
  "by_priority": { "1": { "total": 30, "usable": 19 } },
  "by_platform": { "shopify": { "total": 34, "usable": 34 } },
  "blocked_reasons": { "anti-bot or forbidden (HTTP 403)": 12 }
}
```

### `POST /admin/sync-sites`
Upsert all 120 dataset stores into the `sites` table.
```json
{ "synced": 120 }
```

### `POST /admin/force-scrape`
Scrape one priority tier immediately.

Query params: `priority` (1–3, default 1), `query` (optional; otherwise the
scheduler's default query set).
```json
{ "priority": 1, "sites": 19, "results": { "fender stratocaster": 96 } }
```

### `GET /admin/health-check`
```json
{ "status": "ok" }
```

### `GET /admin/health-check/sites`
Live reachability for all stores, or one with `site_key`.
```json
{ "reachable": 108, "total": 120, "sites": { "thomann": true } }
```

## Schemas (`api/schemas.py`)

`OfferOut`, `SearchResponse`, `PricingRequestOffer`, `PricingResponse`,
`SiteStatus`. Used for request validation and response serialization.

> Not yet implemented (planned in spec): `/instruments/{name}/price-comparison`,
> `/best-deals`, `/trending-instruments`, `/pricing/{instrument_id}` (GET),
> `/admin/scraping-stats`. See [STATUS](STATUS.md).
