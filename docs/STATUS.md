# Status

Last full verification: **26 September 2026** — every one of the 120 stores in
`config/stores.json` was probed and then exercised through its real scraper.

## Coverage

| | Stores | With a working route |
|---|---|---|
| **Total** | 120 | **80** |
| Europe | 37 | 23 |
| USA | 63 | 45 |
| Asia | 20 | 12 |
| Priority 1 (global majors) | 30 | 22 |
| Priority 2 (broad catalogues) | 25 | 17 |
| Priority 3 (niche / workshops) | 65 | 41 |

Route mix across the 80 usable stores: 33 Shopify catalogue feeds, 30 static HTML
parsing (schema.org → embedded JSON → grid detection, or pinned selectors),
7 WooCommerce Store API, 6 Chromium-rendered, 2 Algolia search APIs, 1 Doofinder
search API, 1 official API (Reverb). Thomann keeps its shop-specific parser.

Data quality of the 80: 50 `structured` (API, platform feed, schema.org or
verified selectors), 1 `inline_json` (the shop's own embedded catalogue),
29 `heuristic` (grid read from the page layout).

Anti-bot pass (27 September 2026): 9 of the 19 shops that were blocked by edge
protection now return offers — Sweetwater, Perfect Circuit (Algolia API),
Gear4music (Doofinder API), Bax Music, Scan Pro Audio, Guitar Salon, Vintage
Instruments (Chrome TLS fingerprint), B&H, Strumenti Musicali .net (real Chrome).
All 9 answered in about 11 s in total.

## Functional test

```bash
python -m scripts.test_all_stores      # hits the network, ~20 min for all 120
pytest                                 # offline suite, asserts the last report
```

Latest run (`data/store_test_report.json`):

| Result | Stores | Meaning |
|--------|--------|---------|
| `passed` | 80 | returned at least one offer with a name and a price > 0, with a product URL |
| `skipped` | 40 | no usable route, each with a `blocked_reason` |
| `failed` | 0 | configured as usable but returned nothing |

Queries are chosen per specialty (a drum shop is asked for a snare, a violin
dealer for a violin), up to six per store until one returns offers.

## Why 40 stores are not scraped

| Reason | Stores | Examples |
|--------|--------|----------|
| Interactive anti-bot challenge (needs residential proxy / unlocker) | 3 | Guitar Center (Akamai press-and-hold), The Ukulele Site, Full Compass (Cloudflare Turnstile) |
| robots.txt disallows search | 2 | Music Store, Muziker |
| Site locked, parked or merged | 4 | McCabe's (HTTP 401), Mansons (domain parked), Pro Guitar Shop (now reverb.com), Nakwon (403 outside Korea) |
| Catalogue without public prices ("price on request") | 11 | J & A Beare, Ingles & Hayday, the Conde workshops, Guitarras Ramírez' sister shops, Steinway Hall, Tarisio (auction estimates), Gruhn (now guitars.com) |
| Host does not answer from outside its region | 7 | Musik Hug, Kytary.cz, Sound House, West L.A. Music, Cream City Music, Rayburn, Atlanta Pro Percussion |
| Catalogue not machine-readable (JS-only data, empty or protected API) | 14 | Dale's Drum Shop (API 401), House of Guitars (empty API), Drum-Tec, Lay's, Ikebe, Shimamura, Kurosawa, Parsons Music, Explorers Percussion (spam-injected site) |

Each store's exact reason is in `SITES_CONFIG[id]["blocked_reason"]`, surfaced by
`GET /admin/sites-status` and `GET /admin/coverage`; the probe's full attempt log
per store is in `data/store_probe.json`.

## Known limits

- **Heuristic reads.** 28 stores are parsed by grid detection. It picks the price
  from the price-tagged element and ignores instalments and struck-through
  prices, but a badly structured card can still yield a wrong number — hence the
  `data_quality` flag on every offer.
- **Shopify feeds are capped** at 1000 products per shop (4 × 250). A query that
  matches nothing in that window returns empty for very large catalogues.
- **`sites_config` is a snapshot.** Shops move platform and re-brand (Gruhn →
  guitars.com, Replay → legendsguitars.com during this work), so re-run
  `scripts/probe_stores.py` periodically; it is idempotent.
- **Alembic** is a dependency but no migrations are wired: `init_db()` creates
  tables. The `sites` table gained columns in this revision — delete
  `data/instruments.db` in dev, or add a migration before deploying.
- **Prices are not stored yet** by the scheduled sweeps: `scrape_priority` records
  per-store scrape status, and search results are returned live. Persisting
  offers into `instruments` / `price_history` is the next step.

## Currency

Prices are converted to EUR with live rates (`utils/currency_converter.py`,
static fallback table). Shopify Markets quotes converted prices per visitor
region, so the Shopify scraper reads the session currency from `/cart.js` rather
than assuming the shop's home currency — otherwise a US shop serving EUR to a
European visitor would be converted twice.

## Honest summary

Coverage is 80/120. The three stores left behind interactive challenges need a
residential proxy or an unlocker (the proxy plumbing is ready); captchas are not
solved. Of the other 37, most publish no prices, are unreachable from this
network, or disallow search in robots.txt.
