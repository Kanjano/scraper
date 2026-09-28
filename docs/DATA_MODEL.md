# Data Model

SQLAlchemy 2.0 typed models (`models/`). Tables are created by `init_db()` on app
startup (`Base.metadata.create_all`). Alembic is listed as a dependency but
migrations are not yet wired (see [STATUS](STATUS.md)).

## Entity overview

```
Site (1) ───< (N) Instrument (1) ───< (N) PriceHistory
                          │
                          └──────────< (N) SuggestedPrice
```

## `Site` — `sites`

Tracks each retailer and its last scrape outcome.

| Column | Type | Notes |
|--------|------|-------|
| `id` | int PK | |
| `site_key` | str(64), unique, indexed | the dataset `id` — the stable join key |
| `name` | str, unique, indexed | display name |
| `url` | str | base URL |
| `country` | str(2) | ISO 3166-1 alpha-2 |
| `area` | str(10), indexed | `europe` / `usa` / `asia` |
| `group_name` | str / null | country (EU), state (US) or UN sub-region (Asia) |
| `city` | str / null | |
| `specialty` | str(40), indexed | `general`, `drums_percussion`, … |
| `store_type` | str(30) | `store`, `online_store`, `marketplace`, `auction_house`, `maker_workshop`, `multi_shop_arcade` |
| `top` | bool | globally known name |
| `platform` | str / null | detected e-commerce platform |
| `currency` | str(3) | ISO code |
| `enabled` | bool | false when the store has no usable route |
| `priority` | int | 1 majors · 2 broad catalogues · 3 niche |
| `last_scrape` | datetime / null | |
| `scrape_status` | str | `pending` / `success` / `empty` / `failed` |
| `blocked_reason` | str / null | why the store is disabled |
| `error_count` | int | default 0 |

`sites` is kept in sync with the dataset by `scheduler.jobs.sync_sites()` (run at
scheduler startup, or `POST /admin/sync-sites`).

Relationship: `Site.instruments` ↔ `Instrument.site`.

## `Instrument` — `instruments`

One row per product per site (the current snapshot).

| Column | Type | Notes |
|--------|------|-------|
| `id` | int PK | |
| `site_id` | FK → sites.id | |
| `name` | str | |
| `brand` | str / null | |
| `category` | str / null | |
| `external_id` | str / null | id on the source site |
| `price_current` | float / null | in site currency |
| `currency` | str(3) | default EUR |
| `price_eur_equivalent` | float / null | normalized |
| `url` | str / null | product URL |
| `rating` | float / null | |
| `reviews` | int | default 0 |
| `stock` | int / null | |
| `created_at` / `updated_at` | datetime | server defaults; `updated_at` on update |

Indexes: `(name, brand)`, `(site_id, category)`, `(updated_at)`.

## `PriceHistory` — `price_history`

Append-only price observations for trend analysis.

| Column | Type | Notes |
|--------|------|-------|
| `id` | int PK | |
| `instrument_id` | FK, indexed | |
| `price` | float | site currency |
| `currency` | str(3) | |
| `site_name` | str | |
| `price_normalized` | float / null | EUR |
| `date` | datetime, indexed | server default now |

Consumed by `MarketAnalyzer.price_trend` and `GET /price-history/{id}`.

## `SuggestedPrice` — `suggested_prices`

Persisted output of the pricing engine.

| Column | Type | Notes |
|--------|------|-------|
| `id` | int PK | |
| `instrument_id` | FK, indexed | |
| `price_suggested` | float | |
| `margin_percentage` | float | |
| `margin_amount` | float | |
| `lowest_price_site` | str / null | |
| `lowest_price_amount` | float / null | |
| `market_avg_price` | float / null | |
| `total_sites_analyzed` | int | |
| `reasoning` | text / null | human-readable explanation |
| `created_at` | datetime | |
| `valid_until` | datetime / null | |

> Note: scraped results are currently aggregated and returned in-memory by the
> orchestrator. Persisting `Instrument` / `PriceHistory` rows from live scrapes
> and writing `SuggestedPrice` rows is the next integration step (see STATUS).
