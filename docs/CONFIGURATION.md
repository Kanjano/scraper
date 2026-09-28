# Configuration

Three layers, deliberately separate:

| File | Contents | Edited by |
|------|----------|-----------|
| `config/stores.json` | the dataset: 120 shops, one object each (`id`, `name`, `area`, `group`, `country`, `us_state`, `city`, `specialty`, `type`, `top`, `url`, `domain`, `local_currency`, `note`) | a human, when a shop opens/closes/moves |
| `config/store_overrides.json` | the scraping surface per store: `platform`, `search_url`, `scraper_type`, `data_quality`, `robots_allows_search`, `enabled`, `blocked_reason`, probe timestamps | `scripts/probe_stores.py` (or by hand) |
| `config/sites_config.py` | merges both into `SITES_CONFIG`, adds defaults (headers, rate limits, priority) and the hand-written `MANUAL_OVERRIDES` | code |

`SITES_CONFIG[store_id]` is what every scraper, job and endpoint reads.

## Dataset fields

`id` is the stable key used everywhere (logs, DB `sites.site_key`, report files).
`domain` must equal the start URL's host without `www.` — enforced by
`tests/test_stores_dataset.py`. `specialty` and `type` are closed vocabularies
(`config.sites_config.SPECIALTIES` / `TYPES`).

## Derived fields

- `priority` — `1` for `top: true` (global majors), `3` for `maker_workshop` /
  `auction_house` / `multi_shop_arcade` (tiny or non-shop catalogues), `2` for the
  rest. Drives the scheduler cadence: 4 h / 12 h / 24 h.
- `rate_limit` — 6 req/min for majors, 4 req/min elsewhere; never below 10 s
  between requests to the same domain.
- `searchable` — a search route is known.
- `enabled` — `false` when the probe could not reach or read the shop; always
  paired with `blocked_reason`.
- `data_quality` — `structured` (JSON feed / schema.org) or `heuristic`
  (grid detection).

## Manual overrides

`MANUAL_OVERRIDES` in `config/sites_config.py` pins routes the probe must not
touch: Thomann (`/it/search_dir.html`), Reverb (official API), Gear4music and
Andertons (Playwright), Swee Lee (the catalogue lives on `sweelee.com.sg`).

## Refreshing the configuration

```bash
python -m scripts.probe_stores                 # all 120 stores
python -m scripts.probe_stores --only thomann,reverb
python -m scripts.probe_stores --no-browser    # skip the Chromium fallback
python -m scripts.test_all_stores              # functional test through the scrapers
```

`probe_stores` writes `config/store_overrides.json` and `data/store_probe.json`
(per-store attempt log); `test_all_stores` writes `data/store_test_report.json`,
which `tests/test_live_stores.py` asserts on.

## Environment (`.env`)

See `.env.example`. Most relevant here:

| Variable | Default | Effect |
|----------|---------|--------|
| `REVERB_API_KEY` | – | raises Reverb API rate limits |
| `USE_PROXY` / `PROXY_LIST` | `False` | round-robin proxies for requests and Chromium |
| `HEADLESS_BROWSER` | `True` | Playwright headless mode |
| `CACHE_ENABLED` / `CACHE_TTL_HOURS` | `True` / `12` | Shopify catalogue cache |
| `BASE_CURRENCY` | `EUR` | normalisation target |
| `SCHEDULER_ENABLED` | `True` | periodic scraping on API startup |
