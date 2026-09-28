# Status

Last full verification: **28 September 2026** — every one of the 120 stores in
`config/stores.json` exercised through its real scraper, after a store-by-store
audit of the search routes (see below).

## Coverage

| | Stores | With a working route |
|---|---|---|
| **Total** | 120 | **74** |
| Europe | 37 | 22 |
| USA | 63 | 41 |
| Asia | 20 | 11 |
| Priority 1 (global majors) | 30 | 22 |
| Priority 2 (broad catalogues) | 25 | 14 |
| Priority 3 (niche / workshops) | 65 | 38 |

Route mix across the 74 usable stores: 33 Shopify catalogue feeds, 21 HTML pages
(schema.org → embedded JSON → grid detection, or pinned selectors), 8
Chromium-rendered (6 of them in a real Chrome), 7 WooCommerce Store API, 4 hosted
search APIs (Algolia ×2, Doofinder, Constructor), 1 official API (Reverb).

Data quality of the 74: 53 `structured` (API, platform feed, schema.org or
verified selectors), 1 `inline_json`, 20 `heuristic` (grid read from the layout).

### Route audit (28 September 2026)

"Fender custom shop" was searched in every shop, and two unrelated queries
("gibson", "yamaha") were compared per HTML shop: a route whose results do not
change with the query is not searching.

- **Fixed** (real search route, API or selectors): Andertons (Constructor.io; the
  old search page answers 404), Guitar Guitar, The Guitar Sanctuary, Musik
  Produktiv, Session, BigBoss, Digimart, Thomsun, Furtados, Carter Vintage, and
  Music & Arts (prices had no currency sign; grid detection read a $299 banner
  for every item). Thomann now carries product photos.
- **Disabled** — search ignores the query and the shop builds its results in the
  browser: Stars Music, Bernunzio, Forks Drum Closet, Saxquest, Melody House.
  Musician's Friend: now behind the same Akamai challenge as Guitar Center.
- Shops with relevant results for "fender custom shop": 39 → 47. The coverage
  total drops from 80 to 74 because six shops previously counted as working
  returned the same products whatever was searched.

Anti-bot (27 September 2026): shops behind edge walls are read through their
public search APIs (Sweetwater, Perfect Circuit, Gear4music, Andertons), a
Chrome TLS fingerprint (Bax Music, Scan, Guitar Salon, Vintage Instruments…) or
a real Chrome (B&H, Strumenti Musicali .net, Guitar Guitar, Musik Produktiv…).

## Functional test

```bash
python -m scripts.test_all_stores      # hits the network, ~20 min for all 120
pytest                                 # offline suite, asserts the last report
```

Latest run (`data/store_test_report.json`, 28 September 2026):

| Result | Stores | Meaning |
|--------|--------|---------|
| `passed` | 74 | returned at least one offer with a name and a price > 0, with a product URL |
| `skipped` | 46 | no usable route, each with a `blocked_reason` |
| `failed` | 0 | configured as usable but returned nothing |

Queries are chosen per specialty (a drum shop is asked for a snare, a violin
dealer for a violin), up to six per store until one returns offers.

## Why 46 stores are not scraped

| Reason | Stores | Examples |
|--------|--------|----------|
| Interactive anti-bot challenge (needs residential proxy / unlocker) | 4 | Guitar Center (Akamai press-and-hold), Musician's Friend (Akamai), The Ukulele Site, Full Compass (Cloudflare Turnstile) |
| Search ignores the query; results built in the browser | 5 | Stars Music, Bernunzio, Forks Drum Closet, Saxquest, Melody House |
| robots.txt disallows search | 2 | Music Store, Muziker |
| Site locked, parked or merged | 4 | McCabe's (HTTP 401), Mansons (domain parked), Pro Guitar Shop (now reverb.com), Nakwon (403 outside Korea) |
| Catalogue without public prices ("price on request") | 11 | J & A Beare, Ingles & Hayday, the Conde workshops, Guitarras Ramírez' sister shops, Steinway Hall, Tarisio (auction estimates), Gruhn (now guitars.com) |
| Host does not answer from outside its region | 7 | Musik Hug, Kytary.cz, Sound House, West L.A. Music, Cream City Music, Rayburn, Atlanta Pro Percussion |
| Catalogue not machine-readable (JS-only data, empty or protected API) | 14 | Dale's Drum Shop (API 401), House of Guitars (empty API), Drum-Tec, Lay's, Ikebe, Shimamura, Kurosawa, Parsons Music, Explorers Percussion (spam-injected site) |

Each store's exact reason is in `SITES_CONFIG[id]["blocked_reason"]`, surfaced by
`GET /admin/sites-status` and `GET /admin/coverage`; the probe's full attempt log
per store is in `data/store_probe.json`.

## Known limits

- **Heuristic reads.** 20 stores are parsed by grid detection. It picks the price
  from the price-tagged element and ignores instalments and struck-through
  prices, but a badly structured card can still yield a wrong number — hence the
  `data_quality` flag on every offer.
- **Shopify feeds are capped** at 1000 products per shop (4 × 250). A query that
  matches nothing in that window returns empty for very large catalogues
  (e.g. Woodbrass: its Fender Custom Shop items sit beyond the window).
- **Discounts are as stated by the shops** (list/compare-at prices); some shops
  show a permanent "compare at" price.
- **Search time** grows with the number of shops (1–3 minutes for all of them,
  longer for non-English queries, which are sent twice). Narrow by area to speed up.
- **Peach Guitars'** search page shows a fixed showcase: the relevance filter
  keeps only matching items, so coverage there is partial.
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

Coverage is 74/120, every one of them verified to actually search what is
typed. The four stores behind interactive challenges need a residential proxy
or an unlocker (the proxy plumbing is ready); captchas are not solved. Of the
other 42, most publish no prices, are unreachable from this network, disallow
search in robots.txt, or build their search results in the browser in a way
that cannot be read.
