# Testing

Four layers, from fast and offline to slow and live. Run the first two before
every commit, the live test before a release and monthly.

| Layer | Command | Network | Time |
|-------|---------|---------|------|
| Unit / integration (offline) | `pytest` | no | ~10 s |
| Self-checks of the search logic | `python -m scrapers.relevance` · `python -m scrapers.query_translation` | no (model loaded locally) | seconds |
| Live store test | `python -m scripts.test_all_stores` | yes, all shops | ~20 min |
| Route discovery | `python -m scripts.probe_stores [--only id]` | yes | ~20 min for all |
| Container smoke | build + run, see below | yes | minutes |

Set `SCHEDULER_ENABLED=False` when running tests locally so the app does not
start periodic scrapes.

## Offline suite (`pytest`, 228 tests)

| File | Covers |
|------|--------|
| `tests/test_api.py` | root JSON banner; pricing endpoint; public health; **admin token** (closed when unset, 401 without/with wrong token, Bearer and header accepted) and `/metrics`; **SSE stream** event order and final payload; **favicon** letter fallback and 404; **contact** delivery (To, Reply-To, body), recipient never in the page, invalid input, header injection in name/e-mail, honeypot, rate limit (429), unconfigured (503) |
| `tests/test_i18n.py` | page language for ~40 countries on every continent, multilingual countries resolved by `Accept-Language`, fallbacks, `?lang` + cookie, right-to-left, all 18 languages render complete, GeoIP lookup from the client IP |
| `tests/test_relevance.py` | every query word required, accessories ranked last, lowest price/average from items only, local translation to English, shop-wide list prices not counted as deals |
| `tests/test_extractors.py` | schema.org JSON-LD and microdata, embedded JSON, grid detection (chrome, financing, instalments, split prices), parser priority |
| `tests/test_parsers.py` | price formats (EU/US groupings, currency signs, Turkish thousands, spaces) |
| `tests/test_scrapers_offline.py` | Shopify (local filter, cheapest variant, presentment currency), WooCommerce (minor units), structured scraper chain, Algolia and Doofinder mapping — all with fake responses |
| `tests/test_sites_config.py` | every store has sane config (rate limit, UA, routes templated or POST forms or feeds), disabled stores say why |
| `tests/test_stores_dataset.py` | the 120-shop dataset: ids, domains, enums, areas |
| `tests/test_proxy.py` | proxy pool parsing, rotation, requests/Playwright shapes |
| `tests/test_pricing.py` | suggested-price engine |
| `tests/test_live_stores.py` | assertions on the **last live report** (`data/store_test_report.json`): no failures, product links, every area covered, skipped stores documented |

## Self-checks

`scrapers/relevance.py` and `scrapers/query_translation.py` carry `assert`
blocks in `__main__` covering the tricky cases (prefix matches, CJK,
"for …" accessories, "w/ case" features, sheet music, glossary vs. model,
"sax alto" not becoming a viola, 4/4 kept). Run them after changing any rule;
they print `ok`.

## Live store test

```bash
python -m scripts.test_all_stores                   # all 120 stores
python -m scripts.test_all_stores --only thomann,reverb
```

Each usable store is searched with queries suited to its specialty (a drum shop
gets "snare", a violin dealer "violin"), up to six until one returns offers;
a store passes with at least one offer with a name, a price > 0 and a URL. The
report `data/store_test_report.json` is what `tests/test_live_stores.py` checks.
Latest numbers in [STATUS](STATUS.md).

### Checking that a route really searches

A route can pass (it returns products) and still ignore the query. Compare two
unrelated queries on the same shop — see [SCRAPERS](SCRAPERS.md#checking-that-a-route-really-searches).
The 28 September 2026 audit found and fixed or disabled every such route.

## Front-end checks

- **Demo mode** (localhost only): `/?demo=fast|slow|empty|error|partial&q=…`
  replays fake event streams to exercise every UI state without scraping.
- **Screenshots**: drive the page with Playwright at 1440 px and 390 px, light
  and dark, reduced motion, and `?lang=ar` for right-to-left.
- **Layout shift and long tasks**: a `PerformanceObserver` for `layout-shift`
  and `longtask` during a real search (measured CLS ≈ 0.005; no task > 50 ms at
  4× CPU slowdown during the search).
- **Lighthouse**: `npx lighthouse http://localhost:8000/?lang=it` — targets ≥ 90
  on Performance, Accessibility, Best Practices (measured 99 / 100 / 100 on the
  home page, 99 / 100 / 93 on results — the 93 comes from shops' low-resolution
  favicons).

## Container smoke test

```bash
docker build -t instrinder:test .
docker run -d --name instrinder-test -p 8001:8000 --shm-size=1g \
  -e SCHEDULER_ENABLED=False instrinder:test
docker inspect -f '{{.State.Health.Status}}' instrinder-test        # healthy
curl -s localhost:8001/health                                         # {"status":"ok"}
curl -sN "localhost:8001/search/stream?query=fender&sites=thomann,sweetwater" | grep '^event:'
docker rm -f instrinder-test
```

Verified on arm64: healthy, non-root user, SSE events, stealth shops through the
bundled-Chromium fallback.

## Contact form end to end

Point the app at a local SMTP sink and submit the form:

```bash
pip install aiosmtpd
python -m aiosmtpd -n -l 127.0.0.1:8025 &
SMTP_HOST=127.0.0.1 SMTP_PORT=8025 SMTP_SECURITY=none SMTP_USER= \
CONTACT_EMAIL=you@example.com python main.py
```

The message printed by the sink must be addressed to `CONTACT_EMAIL` with the
visitor's address in `Reply-To`.

## Lint

`ruff check .` (configuration in the project defaults).
