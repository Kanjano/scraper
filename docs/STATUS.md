# Status

Last full verification: **28 September 2026** — every one of the 120 stores in
`config/stores.json` exercised through its real scraper, after a store-by-store
audit of the search routes (see below).

## Coverage

| | Stores | With a working route |
|---|---|---|
| **Total** | 120 | **76** |
| Europe | 37 | 23 |
| USA | 63 | 42 |
| Asia | 20 | 11 |
| Priority 1 (global majors) | 30 | 22 |
| Priority 2 (broad catalogues) | 25 | 15 |
| Priority 3 (niche / workshops) | 65 | 39 |

Route mix across the 76 usable stores: 33 Shopify catalogue feeds (with
brand collections for catalogues over 1000 products), 22 HTML pages (schema.org
→ embedded JSON → grid detection, or pinned selectors; one POST search form),
8 Chromium-rendered (6 of them in a real Chrome), 7 WooCommerce Store API, 5
hosted search APIs (Algolia ×2, Doofinder ×2, Constructor), 1 official API (Reverb).

Data quality of the 76: 54 `structured` (API, platform feed, schema.org or
verified selectors), 1 `inline_json`, 21 `heuristic` (grid read from the layout).

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
  browser: Bernunzio, Forks Drum Closet, Melody House (no product data even in
  a real Chrome). Stars Music (Doofinder API) and Saxquest (POST search form)
  were recovered the same day.
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
| `passed` | 76 | returned at least one offer with a name and a price > 0, with a product URL |
| `skipped` | 44 | no usable route, each with a `blocked_reason` |
| `failed` | 0 | configured as usable but returned nothing |

Queries are chosen per specialty (a drum shop is asked for a snare, a violin
dealer for a violin), up to six per store until one returns offers.

## Why 44 stores are not scraped

| Reason | Stores | Examples |
|--------|--------|----------|
| Interactive anti-bot challenge (needs residential proxy / unlocker) | 4 | Guitar Center (Akamai press-and-hold), Musician's Friend (Akamai), The Ukulele Site, Full Compass (Cloudflare Turnstile) |
| Search ignores the query; results built in the browser | 3 | Bernunzio, Forks Drum Closet, Melody House |
| robots.txt disallows search | 2 | Music Store, Muziker |
| Site locked, parked or merged | 4 | McCabe's (HTTP 401), Mansons (domain parked), Pro Guitar Shop (now reverb.com), Nakwon (403 outside Korea) |
| Catalogue without public prices ("price on request") | 11 | J & A Beare, Ingles & Hayday, the Conde workshops, Guitarras Ramírez' sister shops, Steinway Hall, Tarisio (auction estimates), Gruhn (now guitars.com) |
| Host does not answer from outside its region | 7 | Musik Hug, Kytary.cz, Sound House, West L.A. Music, Cream City Music, Rayburn, Atlanta Pro Percussion |
| Catalogue not machine-readable (JS-only data, empty or protected API) | 14 | Dale's Drum Shop (API 401), House of Guitars (empty API), Drum-Tec, Lay's, Ikebe, Shimamura, Kurosawa, Parsons Music, Explorers Percussion (spam-injected site) |

Each store's exact reason is in `SITES_CONFIG[id]["blocked_reason"]`, surfaced by
`GET /admin/sites-status` and `GET /admin/coverage`; the probe's full attempt log
per store is in `data/store_probe.json`.

## Known limits

- **Heuristic reads.** 21 stores are parsed by grid detection. It picks the price
  from the price-tagged element and ignores instalments and struck-through
  prices, but a badly structured card can still yield a wrong number — hence the
  `data_quality` flag on every offer.
- **Shopify feeds are read up to 1000 products per shop** (4 × 250). For larger
  catalogues the shop's collections fill the gap: when the query names a
  collection ("fender", "fender custom shop") its own feed is read too. The
  first search of such a shop lists its collections once (≈ 100 s for
  Woodbrass's 2000, then cached 12 h). A product in no collection named by the
  query can still be missed.
- **Discounts are as stated by the shops.** A shop showing a cut on ≥ 80 % of
  what it returned (at least 5 items) is showing a list price: those offers are
  flagged `discount_everywhere` and kept out of the deals column.
- **Search time** grows with the number of shops (1–3 minutes for all of them,
  longer for non-English queries, which are sent twice). Narrow by area to speed up.
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

Coverage is 76/120, every one of them verified to actually search what is
typed. The four stores behind interactive challenges need a residential proxy
or an unlocker (the proxy plumbing is ready); captchas are not solved. Of the
other 40, most publish no prices, are unreachable from this network, disallow
search in robots.txt, or build their search results in the browser in a way
that cannot be read.
