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
touch or cannot find: Thomann (`/it/search_dir.html`), Reverb (official API),
Sweetwater / Perfect Circuit (Algolia), Gear4music (Doofinder), Andertons
(Constructor.io), Swee Lee and Ishibashi (their Shopify storefronts), the shops
behind edge anti-bot walls, and the routes fixed by hand after the store audit
(Guitar Guitar, Guitar Sanctuary, Musik Produktiv, Session, BigBoss, Digimart,
Thomsun, Furtados, Music & Arts). A manual `search_url` supersedes the probe.

Keys an override may set:

| Key | Meaning |
|-----|---------|
| `platform` | informational (`shopify`, `woocommerce`, `magento`, `bigcommerce`, `custom`…) |
| `scraper_type` | `shopify` · `woocommerce` · `structured` · `requests` · `playwright` · `api` · `algolia` · `doofinder` · `constructor` |
| `search_url` | route with `{query}` (or the Shopify feed) |
| `selectors` | CSS selectors: `product_container`, `name`, `price`, optional `original_price`, `url` (`:scope` = the card is the link), `image`, `brand` |
| `data_quality` | `structured` · `inline_json` · `heuristic` |
| `impersonate` | `true` = requests with a Chrome TLS fingerprint (curl_cffi) |
| `stealth` | `true` (playwright only) = real Google Chrome via patchright |
| `session_setup` | one POST before searching (`{"url", "data"}`), e.g. pin a display currency |
| `search_post` | the search is a POST form: `{"field": "{query}"}` sent to `search_url` (Saxquest) |
| `algolia` / `doofinder` / `constructor` | the public search-API settings of that shop (see [SCRAPERS](SCRAPERS.md)) |
| `enabled` / `blocked_reason` | disable a shop and say why |

`VERIFIED_BLOCKS` holds hand-checked reasons for shops without any route.

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
| `SCHEDULER_ENABLED` | `True` | periodic scraping jobs; set `False` in development |
| `SCRAPER_CONTACT` | – | e-mail or URL added to the scraper's User-Agent, so shops can reach you |
| `GEOIP_DB` | `data/dbip-country-lite.mmdb` | offline IP → country file for the page language (optional) |
| `SEMANTIC_MODEL` | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | local model for cross-language matching; empty = literal only |
| `MODELS_DIR` | `data/models` | where the model is downloaded once |

### Contact form

The recipient lives only in `.env`, never in code or in the page.

| Variable | Default | Effect |
|----------|---------|--------|
| `CONTACT_EMAIL` | – | who receives the messages; empty → `/contact` answers 503 |
| `SMTP_HOST` | – | outgoing mail server; empty → 503 |
| `SMTP_PORT` | `587` | |
| `SMTP_SECURITY` | `starttls` | `starttls` · `ssl` (port 465) · `none` |
| `SMTP_USER` / `SMTP_PASSWORD` | – | login (Gmail: an *app password*) |
| `CONTACT_FROM` | `SMTP_USER` | sender address |
| `CONTACT_RATE_LIMIT` / `CONTACT_RATE_WINDOW_S` | `3` / `600` | messages per client IP per window |

Gmail example: `SMTP_HOST=smtp.gmail.com`, `SMTP_PORT=587`,
`SMTP_SECURITY=starttls`, `SMTP_USER=<address>`, `SMTP_PASSWORD=<app password>`.
| `CACHE_ENABLED` / `CACHE_TTL_HOURS` | `True` / `12` | Shopify catalogue cache |
| `BASE_CURRENCY` | `EUR` | normalisation target |
| `SCHEDULER_ENABLED` | `True` | periodic scraping on API startup |
