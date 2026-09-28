# Documentation — INSTRINDER

INSTRINDER is a worldwide musical-instrument price search over a dataset of
**120 internationally known shops** (Europe 37 · USA 63 · Asia 20). It searches
every shop it can read, keeps the offers that match the query, normalises prices
to EUR, flags discounts, and serves the results through a web page and a
FastAPI service.

## Index

| Doc | Contents |
|-----|----------|
| [GUIDA](GUIDA.md) | **user and operator guide** (Italian): using the site, installing, `.env`, maintenance, troubleshooting |
| [FRONTEND](FRONTEND.md) | the web page: layout, live search states, deals column, contact form, languages, design tokens, accessibility, demo mode |
| [SEARCH](SEARCH.md) | query translation, relevance filter, accessories, relevance score, discounts and deals, sorting |
| [API](API.md) | REST endpoints, SSE stream events, contact, parameters, responses |
| [ARCHITECTURE](ARCHITECTURE.md) | layered design, request/data flow, module map |
| [CONFIGURATION](CONFIGURATION.md) | the store dataset, overrides and their keys, `.env` settings |
| [SCRAPERS](SCRAPERS.md) | route tiers, scraper classes, fields returned, adding or fixing a shop |
| [ANTIBOT_PROXY](ANTIBOT_PROXY.md) | bot-protection findings per shop, proxy support |
| [DATA_MODEL](DATA_MODEL.md) | SQLAlchemy models and relationships |
| [PRICING](PRICING.md) | suggested-price algorithm, market analysis |
| [STATUS](STATUS.md) | coverage per area/tier, live test results, known limits |

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
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
cp .env.example .env
python main.py
```

## Refresh the store routes

```bash
python -m scripts.probe_stores       # re-discover platform + search route per shop
python -m scripts.test_all_stores    # verify every shop through its real scraper
```
