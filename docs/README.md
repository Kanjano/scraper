# Documentation — Strumenti Musicali Scraper

Worldwide musical-instrument price aggregator over a dataset of **120
internationally known shops** (Europe 37 · USA 63 · Asia 20). It searches every
shop it can read, normalises prices to EUR, computes a competitive suggested
price, and exposes everything through a FastAPI service.

This folder documents the project **as built to date**. Where a component is
planned in the spec but not yet implemented, it is marked explicitly (see
[STATUS](STATUS.md)).

## Index

| Doc | Contents |
|-----|----------|
| [ARCHITECTURE](ARCHITECTURE.md) | Layered design, request/data flow, module map |
| [CONFIGURATION](CONFIGURATION.md) | the store dataset, probed overrides, `.env` settings |
| [DATA_MODEL](DATA_MODEL.md) | SQLAlchemy models and relationships |
| [SCRAPERS](SCRAPERS.md) | Route tiers, scraper classes, adding or fixing a shop |
| [API](API.md) | REST endpoints, parameters, responses |
| [PRICING](PRICING.md) | Suggested-price algorithm, market analysis |
| [ANTIBOT_PROXY](ANTIBOT_PROXY.md) | Bot-protection findings, proxy support |
| [STATUS](STATUS.md) | Coverage per area/tier, functional-test results, known limits |

## TL;DR

- **Stack:** Python 3.11+ (dev/verified on 3.12), FastAPI, SQLAlchemy 2.0,
  APScheduler, requests + BeautifulSoup, Playwright (Chromium) for JS sites.
- **Coverage (live-verified 2026-09-26):** 71 of 120 shops return offers; the
  other 49 are disabled with a recorded reason (anti-bot, no public prices,
  unreachable). Routes: Shopify feeds, WooCommerce Store API, Reverb's API,
  schema.org, embedded catalogue JSON, grid detection, Chromium rendering.
- **Tests:** 170 passing offline (`pytest`), plus the live sweep
  `python -m scripts.test_all_stores` (~20 min, writes
  `data/store_test_report.json`).
- **Run:** `python main.py` → http://localhost:8000 (interactive docs at `/docs`).

## Quick start

```bash
cd strumenti-musicali-scraper
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium      # only needed for JS-rendered sites
cp .env.example .env
python main.py
```

## Refresh the store routes

```bash
python -m scripts.probe_stores       # re-discover platform + search route per shop
python -m scripts.test_all_stores    # verify every shop through its real scraper
```
