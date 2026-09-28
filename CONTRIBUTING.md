# Contributing

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium && patchright install chromium
cp .env.example .env          # set SCHEDULER_ENABLED=False for development
python main.py                # http://localhost:8000
```

Try the UI without scraping: `http://localhost:8000/?demo=slow&q=gibson`.

## Before a commit

```bash
pytest                                   # offline suite
python -m scrapers.relevance             # if you touched search rules
python -m scrapers.query_translation     # if you touched translation
ruff check .
```

Before a release, run the live test: `python -m scripts.test_all_stores`
([TESTING](docs/TESTING.md)).

## Conventions

- **Code style**: match the surrounding code; comments explain *why*. Deliberate
  simplifications with a known ceiling are marked `ponytail:` with the upgrade
  path.
- **No new dependency** for what the standard library or an installed package
  already does.
- **Commits**: Conventional Commits (`feat:`, `fix:`, `docs:`, `refactor:` …),
  subject ≤ 72 characters, body explaining why.
- **Secrets** never in code or docs; configuration goes through
  `config/settings.py` and `.env.example` (empty placeholder).
- **Front end**: plain HTML/CSS/JS; tokens in `app.css`; new strings in every
  language of `api/web/translations.json`; animate only `transform`, `opacity`,
  `clip-path`; keep contrast AA and reduced-motion variants ([DESIGN](docs/DESIGN.md)).

## Common tasks

| Task | Where |
|------|-------|
| Add or fix a shop | [SCRAPERS](docs/SCRAPERS.md#adding-or-fixing-a-store) — dataset entry, probe, manual override, live test |
| Support a new search API or platform | a `BaseScraper` subclass in `scrapers/sites/`, registered in `SCRAPER_TYPES` |
| Tune relevance or accessories | `scrapers/relevance.py`, then its self-checks and `tests/test_relevance.py` |
| Improve query translation | `scrapers/data/gear_glossary.json` |
| Add a UI language | a block in `api/web/translations.json` with all keys |
| Change the design | tokens in `api/web/static/app.css`; document in `docs/DESIGN.md` |

## Documentation

Update the relevant page in `docs/` together with the change; `docs/STATUS.md`
after a live test.
