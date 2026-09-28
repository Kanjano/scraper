# INSTRINDER

Musical-instrument price search across **120 internationally known shops**
(Europe 37 · USA 63 · Asia 20). Type what you want — in any of 18 languages —
and INSTRINDER searches every shop it can read, keeps the offers that really
match, converts prices to euro, flags discounts and ranks the results.

- **Web page** in the style of a search engine: live progress while shops
  answer, sorting (relevance, price ↑/↓, A–Z), area tabs, a **deals** column
  with product photos linking to the retailer, a contact form, light/dark theme.
- **REST API** (FastAPI): search, live search stream, store coverage, pricing.
- **Local intelligence, no external AI service**: cross-language matching with
  an offline multilingual model, query translation through a gear glossary.

📖 Full documentation: [`docs/`](docs/README.md) · 🇮🇹 **Guida all'utilizzo:
[docs/GUIDA.md](docs/GUIDA.md)**

---

## Quick start

Docker (multi-arch, includes browsers and the search model):

```bash
git clone https://github.com/Kanjano/scraper.git instrinder && cd instrinder
cp .env.example .env                 # then edit it — see Configuration
docker compose up -d --build         # http://localhost:8000
```

Local Python:

```bash
git clone https://github.com/Kanjano/scraper.git instrinder && cd instrinder
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium          # JS-rendered shops
patchright install chromium          # "stealth" shops (uses Google Chrome when installed)
cp .env.example .env                 # then edit it — see Configuration
python main.py                       # http://localhost:8000   (API docs: /docs)
```

The first start downloads the search model once (~240 MB into `data/models/`).
Set `SCHEDULER_ENABLED=False` in `.env` during development to skip the periodic
background scraping.

## Using the site (short guide)

1. Open http://localhost:8000 and type a brand, model or instrument
   (`fender stratocaster custom shop`, `violino 4/4`). Optionally pick an area or
   "major shops only". Press Enter.
2. Watch the progress: phases, shops answering, first results arriving. **Stop**
   or **Esc** interrupts and keeps what arrived.
3. Read the results: price in euro, original price and currency, country,
   struck previous price and **−N%** when the shop states a discount; parts and
   accessories are tagged and listed last.
4. **Sort by** relevance, price ascending/descending or name; filter with the
   area tabs; **⋮** copies the link or the raw data.
5. The right column lists the biggest **deals** — click a card to open the
   product on the retailer's site.
6. Share the address bar: it holds the query, area and sort
   (`?q=…&area=europe&sort=price_asc`).

Details, screenshots of every state and troubleshooting:
[docs/GUIDA.md](docs/GUIDA.md) (Italian), [docs/FRONTEND.md](docs/FRONTEND.md).

## Configuration

Everything is set in `.env` (never committed; template in `.env.example`).

| Area | Variables |
|------|-----------|
| Development | `SCHEDULER_ENABLED=False` |
| Scraper identity | `SCRAPER_CONTACT` (e-mail or URL added to the User-Agent) |
| Contact form | `CONTACT_EMAIL` (recipient, only here), `SMTP_HOST`, `SMTP_PORT`, `SMTP_SECURITY`, `SMTP_USER`, `SMTP_PASSWORD`, `CONTACT_FROM`, `CONTACT_RATE_LIMIT`, `CONTACT_RATE_WINDOW_S` |
| Page language | `GEOIP_DB` (optional offline IP → country file) |
| Search | `SEMANTIC_MODEL` (empty = literal matching only), `MODELS_DIR` |
| Hard-to-reach shops | `USE_PROXY`, `PROXY_LIST`, `HEADLESS_BROWSER` |
| APIs | `REVERB_API_KEY` (optional), `CURRENCY_API_KEY` |

Contact form with Gmail: `SMTP_HOST=smtp.gmail.com`, `SMTP_PORT=587`,
`SMTP_SECURITY=starttls`, `SMTP_USER=<address>`, `SMTP_PASSWORD=<app password>`.
Without `SMTP_HOST` the form answers "not available" instead of losing messages.
The recipient address never appears in the page.

GeoIP file (optional, monthly, CC BY 4.0 — attribution is in the page footer):

```bash
curl -s https://download.db-ip.com/free/dbip-country-lite-$(date +%Y-%m).mmdb.gz \
  | gunzip > data/dbip-country-lite.mmdb
```

Full reference: [docs/CONFIGURATION.md](docs/CONFIGURATION.md).

## API at a glance

| Endpoint | Purpose |
|----------|---------|
| `GET /` | the web page (browsers) or a JSON banner (API clients) |
| `GET /search?query=…` | search every readable shop; filters `area`, `priority`, `sites` |
| `GET /search/stream?query=…` | the same search as Server-Sent Events (live progress) |
| `POST /contact` | contact form → e-mail |
| `GET /favicon/{site_key}` | shop icon served from our origin |
| `GET /stores` · `GET /admin/coverage` | the dataset and why some shops are not readable |
| `POST /pricing` · `GET /market-analysis` | suggested price, market overview |

Each offer carries `price_eur`, `original_price` / `discount_pct`, `image`,
`relevance`, `is_accessory`, `data_quality`. Full reference:
[docs/API.md](docs/API.md).

## How it works

```
page / API ─► orchestrator ─► ~76 shops in parallel ─► normalize (EUR, discount)
                 │                                          │
      query translation (local)          relevance filter · accessories · score
                                                            │
                                     ranked results · deals · live SSE events
```

- **Per-shop routes**, most structured first: official/hosted search APIs
  (Reverb, Algolia, Doofinder, Constructor), Shopify and WooCommerce feeds,
  schema.org, embedded JSON, grid detection, CSS selectors, real-browser
  rendering. Decided by `scripts/probe_stores.py`, pinned by hand where needed.
- **Anti-bot**: public search APIs, Chrome TLS fingerprint, real Chrome for
  non-interactive challenges; interactive challenges are not solved.
- **Relevance**: every word must match (literally, by prefix, or by meaning in
  another language); accessories ranked last; see [docs/SEARCH.md](docs/SEARCH.md).

## Project layout

```
api/           FastAPI app, routes (search + stream, contact, favicons, pricing,
               analytics, admin), i18n, web/ (page template, translations,
               static CSS/JS/fonts)
config/        stores.json (dataset), store_overrides.json (probed routes),
               sites_config.py (merge + manual overrides), settings, DB engine
scrapers/      base scraper, parsers, schema.org / inline JSON / grid extraction,
               relevance.py, query_translation.py, data/ (glossary, vocabulary),
               sites/ (one scraper per platform + registry)
scheduler/     orchestrator (parallel search, events, aggregation), jobs
scripts/       probe_stores.py (route discovery), test_all_stores.py (live test)
pricing/ models/ utils/ cache/ monitoring/   supporting layers
tests/         pytest suite (offline)
docs/          documentation
```

## Maintenance and tests

```bash
pytest                                  # offline suite
python -m scripts.test_all_stores       # live: every shop through its real scraper (~20 min)
python -m scripts.probe_stores --only <id>   # re-discover one shop's search route
```

Shops change platforms and search pages; re-run the probe and the live test
periodically. Status and coverage: [docs/STATUS.md](docs/STATUS.md).

## Documentation

| Doc | Contents |
|-----|----------|
| [FUNCTIONAL](docs/FUNCTIONAL.md) | functional specification: features, acceptance criteria, business rules |
| [DESIGN](docs/DESIGN.md) | design system: identity, colour and contrast, type, motion, components, layout, accessibility |
| [INFRASTRUCTURE](docs/INFRASTRUCTURE.md) | sizing, Docker, reverse proxy for SSE, security checklist, scaling, observability, maintenance |
| [SECURITY](docs/SECURITY.md) · [TESTING](docs/TESTING.md) | security and privacy; test layers and how to run them |
| [GUIDA](docs/GUIDA.md) | user and operator guide (Italian) |
| [FRONTEND](docs/FRONTEND.md) | web page: layout, live search, deals, contact, languages, accessibility |
| [SEARCH](docs/SEARCH.md) | translation, relevance filter, accessories, discounts, sorting |
| [API](docs/API.md) | endpoints, parameters, responses, SSE events |
| [ARCHITECTURE](docs/ARCHITECTURE.md) | layers, request flow, module map |
| [CONFIGURATION](docs/CONFIGURATION.md) | dataset, store overrides, `.env` |
| [SCRAPERS](docs/SCRAPERS.md) | route tiers, scraper classes, adding or fixing a shop |
| [ANTIBOT_PROXY](docs/ANTIBOT_PROXY.md) | protections per shop, proxies |
| [PRICING](docs/PRICING.md) · [DATA_MODEL](docs/DATA_MODEL.md) | suggested price, database models |
| [STATUS](docs/STATUS.md) | coverage, live test results, known limits |

Also: [CONTRIBUTING](CONTRIBUTING.md) · [CHANGELOG](CHANGELOG.md).

> **Before going online**: `/admin/*` has no authentication — restrict it at
> the reverse proxy ([INFRASTRUCTURE](docs/INFRASTRUCTURE.md#reverse-proxy)).
