# Documentation — INSTRINDER

INSTRINDER is a worldwide musical-instrument price search over a dataset of
**120 internationally known shops** (Europe 37 · USA 63 · Asia 20). It searches
every shop it can read, keeps the offers that match the query, normalises prices
to EUR, flags discounts, and serves the results through a web page and a
FastAPI service.

## Index

**Start here**: functional overview in [FUNCTIONAL](FUNCTIONAL.md), system design
in [ARCHITECTURE](ARCHITECTURE.md), running it in [INFRASTRUCTURE](INFRASTRUCTURE.md),
the look and feel in [DESIGN](DESIGN.md); Italian users: [GUIDA](GUIDA.md).

| Doc | Area | Contents |
|-----|------|----------|
| [FUNCTIONAL](FUNCTIONAL.md) | functional | purpose, actors, features with acceptance criteria, business rules, edge cases |
| [GUIDA](GUIDA.md) | functional | **user and operator guide** (Italian): using the site, installing, `.env`, maintenance, troubleshooting |
| [ARCHITECTURE](ARCHITECTURE.md) | technical | context and sequence diagrams, layers, module map, data flow, concurrency, caching, errors, extension points |
| [SEARCH](SEARCH.md) | technical | query translation, relevance filter, accessories, relevance score, discounts and deals, sorting |
| [SCRAPERS](SCRAPERS.md) | technical | route tiers, scraper classes, fields returned, adding or fixing a shop |
| [API](API.md) | technical | REST endpoints, SSE events, contact, parameters, responses |
| [CONFIGURATION](CONFIGURATION.md) | technical | dataset, store overrides and their keys, every `.env` setting |
| [DATA_MODEL](DATA_MODEL.md) · [PRICING](PRICING.md) | technical | database models; suggested price |
| [INFRASTRUCTURE](INFRASTRUCTURE.md) | infrastructure | sizing, Docker, VM/systemd, reverse proxy for SSE, security checklist, scaling, observability, jobs, maintenance, backups |
| [SECURITY](SECURITY.md) | infrastructure | secrets, endpoint exposure, injection, privacy, conduct toward shops |
| [ANTIBOT_PROXY](ANTIBOT_PROXY.md) | infrastructure | protections per shop, proxy support |
| [TESTING](TESTING.md) | quality | offline suite, self-checks, live test, UI and container checks |
| [STATUS](STATUS.md) | quality | coverage, live results, known limits |
| [DESIGN](DESIGN.md) | design | principles, identity, colour tokens and contrast, type, motion, components, layout, states, accessibility, localisation, performance budget |
| [FRONTEND](FRONTEND.md) | design / technical | how the page is built: files, lifecycle, contact, languages, demo mode |

## TL;DR

- **Stack:** Python 3.11+ (verified on 3.12), FastAPI, SQLAlchemy 2.0,
  APScheduler, requests / curl_cffi + BeautifulSoup, Playwright and patchright
  (Google Chrome) for JS and protected shops, fastembed (local multilingual
  model), Babel + DB-IP Lite for the page language. Front end: plain HTML/CSS/JS,
  no build.
- **Run:** `python main.py` → http://localhost:8000 (API docs at `/docs`).
- **Tests:** `pytest` (offline); live sweep `python -m scripts.test_all_stores`
  (~20 min, writes `data/store_test_report.json`).

## Quick start

```bash
cp .env.example .env && docker compose up -d --build      # Docker
# or
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && playwright install chromium && patchright install chromium
cp .env.example .env && python main.py
```

## Refresh the store routes

```bash
python -m scripts.probe_stores       # re-discover platform + search route per shop
python -m scripts.test_all_stores    # verify every shop through its real scraper
```
