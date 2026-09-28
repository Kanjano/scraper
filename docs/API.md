# API Reference

FastAPI app (`api/main.py`). Interactive docs at `/docs` (Swagger) and `/redoc`.
On startup the app initializes the database and (if `SCHEDULER_ENABLED`) starts
the APScheduler background scheduler; both are torn down on shutdown via the
lifespan handler.

Base URL: `http://localhost:8000`

## Root

### `GET /`
Content negotiation: a browser (`Accept: text/html`) gets the INSTRINDER search
page in the visitor's language (see [FRONTEND](FRONTEND.md)); `?lang=xx` forces
a language, `?q=…&area=…&priority=…&sort=…` opens a search. Any other client
gets the service banner:
```json
{ "service": "strumenti-musicali-scraper", "docs": "/docs" }
```
Response headers: `Content-Language`, `X-Visitor-Country` (when known).

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
  "query": "chitarra elettrica fender",
  "translated_query": "guitar electric fender",
  "sites_queried": 79,
  "total_results": 205,
  "lowest_price": 113.33,
  "lowest_price_site": "Bajaao",
  "market_average": 4498.22,
  "results": [
    {
      "rank": 1,
      "site": "Andertons",
      "site_key": "andertons-music-co",
      "area": "europe",
      "country": "GB",
      "name": "Fender Custom Shop Postmodern Stratocaster",
      "price": 2999.0,
      "currency": "GBP",
      "price_eur": 3508.83,
      "rating": null,
      "url": "https://www.andertons.co.uk/...",
      "data_quality": "structured",
      "is_accessory": false,
      "image": "https://cdn11.bigcommerce.com/...jpg",
      "original_price": 3999.0,
      "original_price_eur": 4678.83,
      "discount_pct": 25,
      "relevance": 0.83
    }
  ],
  "search_time_seconds": 58.4
}
```

- Only offers matching every word of the query (literally, by prefix, or by
  meaning in another language) are returned — see [SEARCH](SEARCH.md).
- Order: items first, accessories after (`is_accessory`), each by EUR price.
  `lowest_price` and `market_average` ignore accessories.
- `translated_query`: the English version also sent to the shops (null when the
  query is already English).
- `original_price` / `discount_pct`: the shop's pre-discount price and the cut
  (0 = not on sale). `image`: product photo URL on the shop's CDN.
- `relevance`: 0..1 fit to the query, used by the page's "sort by relevance".
- `discount_everywhere`: the shop shows a cut on nearly everything it returned
  (a list price, not a sale); such offers are left out of the deals column.
- `data_quality` says how the number was obtained: `structured` (official API,
  JSON feed, schema.org markup or verified selectors), `inline_json` (the shop's
  own embedded catalogue JSON), or `heuristic` (product grid read from the page
  layout — lower confidence).

### `GET /search/stream`
The same search, streamed as **Server-Sent Events** while it runs (same query
parameters as `/search`). Used by the web page for live progress.

| Event | Data |
|-------|------|
| `phase` | `{"id": "prepare"\|"search"\|"filter"\|"rank", "status": "active"\|"done"}` |
| `start` | `{"query", "translated_query", "sites": [{"key", "name", "url", "area"}]}` |
| `site` | one shop answered: `{"key", "name", "status": "ok"\|"empty"\|"error", "error", "offers", "relevant": [offer…], "done", "total"}` |
| `done` | the final `SearchResponse` (ranked) |
| `error` | `{"message"}` |

Comment lines (`: keep-alive`) are sent every 15 s of silence. Closing the
connection cancels shops that have not started yet.

```bash
curl -N "http://localhost:8000/search/stream?query=moog&sites=thomann,reverb"
```

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

## Contact (`api/routes/contact.py`)

### `POST /contact`
Sends a visitor's message by e-mail to `CONTACT_EMAIL` (server configuration —
never exposed to the page). Body:
```json
{ "name": "Ada", "email": "ada@example.com", "message": "Please add a shop in Milan.",
  "website": "", "lang": "it" }
```
`website` is a honeypot (hidden field): when filled the request is accepted
silently and nothing is sent. The visitor's address becomes `Reply-To`.

| Status | Meaning |
|--------|---------|
| 200 `{"ok": true}` | sent |
| 422 | invalid input (empty/long fields, bad e-mail, line breaks in name/e-mail) |
| 429 | rate limit per IP (`CONTACT_RATE_LIMIT` per `CONTACT_RATE_WINDOW_S`) |
| 502 | the SMTP server refused or was unreachable |
| 503 | not configured (`CONTACT_EMAIL` or `SMTP_HOST` empty) |

## Shop icons (`api/routes/favicons.py`)

### `GET /favicon/{site_key}`
The shop's icon served from our origin (fetched once, cached in
`data/cache/favicons/`); an SVG letter badge when the shop has none. `404` for
an unknown shop. Cached by browsers for a week.

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
`ContactIn` (in `api/routes/contact.py`) validates the contact form.

> Not yet implemented (planned in spec): `/instruments/{name}/price-comparison`,
> `/best-deals`, `/trending-instruments`, `/pricing/{instrument_id}` (GET),
> `/admin/scraping-stats`. See [STATUS](STATUS.md).
