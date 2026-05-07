# Search Test Report — 3 Queries

Date: 2026-05-06
Target: validate live-scrape search pipeline (Flask backend, no Django).
Queries tested: `fender mustang`, `gibson les paul`, `friedman`.

---

## 1. Codebase Audit

### 1.1 Stack
- **Framework:** Flask 2.2.5 + Flask-SQLAlchemy + Flask-Login (NOT Django).
- **DB:** SQLite (`backend/instance/scraper.db`). Models: `User`, `SearchHistory` only — **no product table**.
- **Search architecture:** real-time multi-site scraping. No DB-side full-text index.

### 1.2 Search pipeline (entry → result)
1. `POST /api/search` (`backend/app.py:307`) — accepts `{prodotto, siti}`.
2. `normalize_query(raw_query)` (`backend/search_normalizer.py:28`) — lowercase, strip accents via `_ACCENT_MAP`, drop non-alnum, collapse whitespace.
3. Optional save to `SearchHistory` (per-user dedup vs last entry).
4. `run_all_scrapers(norm_query, sites)` (`backend/scraper_service.py:88`) — `ThreadPoolExecutor` with `MAX_WORKERS=2` (env), `SCRAPER_TIMEOUT=90s`. Fan-out to 7 scrapers; one retry on exception (1s sleep, no cleanup_cache during parallel run to avoid driver races).
5. `calculate_discounts(results)` — derives `sconto_percentuale` from `prezzo_originale_numerico`.
6. `apply_referral_links(results, ReferralDBManager)` — rewrites `link` field.
7. `filter_and_rank_results(results, norm_query)` (`backend/scraper_service.py:153`):
   - Strict: keep items where **all tokens** appear in `nome|titolo|name` (`_filter_strict`, `scraper_service.py:140`).
   - If strict yields ≥ `STRICT_MIN_RESULTS=5` → use strict, mode=`strict`.
   - Else fallback to full pool, mode=`fuzzy`.
   - Score each item: `relevance_score = round(rapidfuzz.WRatio(query, name) * 100)`.
   - Sort by `(-relevance_score, parse_price)`.
8. `get_top_discounts(ranked, n=10)`.
9. JSON response: `{results, stats, top_discounts, search_mode, count, normalized_query}`.

### 1.3 Scrapers (7)
| key | display | impl |
|-----|---------|------|
| thomann | Thomann | `scraper_thomann.cerca_thomann` |
| musik_produktiv | Musik Produktiv | `scraper_musik_produktiv.cerca_musik_produktiv` |
| gear4music | Gear4music | `scraper_gear4music.cerca_gear4music` |
| andertons | Andertons | `scraper_andertons.cerca_andertons` |
| centrochitarre | Centro Chitarre | `scraper_centrochitarre.cerca_centrochitarre` |
| tomassone | Tomassone | `scraper_tomassone.cerca_tomassone` |
| strumentimusicali | StrumentiMusicali.net | `scraper_strumentimusicali.search_strumentimusicali` |

Selenium-driven for dynamic sites. Returns `list[dict]` with at least `nome`, `prezzo`, `link`, `sito` (auto-injected if missing).

### 1.4 Match semantics
- **Match field:** ONLY `nome | titolo | name` (`_filter_strict`, lines 140–150). No description/category/brand fields.
- **Operator:** Python `in` on **normalized** lowercased name → `icontains` equivalent. Token-AND, not phrase match.
- **Diacritics:** stripped both query side (`normalize_query`) and indirectly on name side (`fuzzy_match_score` re-normalizes name before WRatio).
- **Stopwords:** `_STOPWORDS` (it/en short words) used by `get_query_tokens`, but NOT by `_filter_strict`. Strict filter uses raw `query.split()`.

### 1.5 Indexes
- DB has no product/search index — irrelevant: search is HTTP-time scrape, not DB query.
- SQLite indexes only via SQLAlchemy defaults (PK on `User.id`, `SearchHistory.id`). `SearchHistory.user_id` lacks explicit index (potential issue for history reads at scale).

---

## 2. Test Results — 3 Base Queries (live scrape)

Run: `backend/test_three_queries.py`. Report JSON: `backend/test_three_queries_report.json`.

### 2.1 Comparative table

| Query | raw | ranked | mode | scrape s | sites OK | sites empty/err |
|---|---|---|---|---|---|---|
| `fender mustang`  | 241 | 195 | strict | 42.46 | Thomann, Gear4music, Musik Produktiv, Centro Chitarre, Tomassone, StrumentiMusicali | Andertons (errore→0) |
| `gibson les paul` | 233 | 217 | strict | 36.78 | Thomann, Musik Produktiv, Centro Chitarre, Tomassone, Andertons, StrumentiMusicali | Gear4music (errore→0) |
| `friedman`        | 144 | 143 | strict | 36.04 | Thomann, Musik Produktiv, Centro Chitarre, Tomassone, StrumentiMusicali, Andertons | Gear4music (errore→0) |

`ranked < raw` because strict filter drops items whose name lacks all tokens (e.g. "Mustang amp combo" fails `fender` token).
Match-field analysis on ranked top-50 each query: `all_tokens_in_nome=50/50` → strict invariant holds.

### 2.2 Top-10 highlights (full list in JSON)

`fender mustang` (top scores 100/95):
- Musik Produktiv "Fender Mustang" €14.90 (100)
- Tomassone "FENDER MUSTANG LTX50" €339 (95)
- Centro Chitarre "Fender Mustang LT 25" €175 (95)
…all 10 contain both tokens.

`gibson les paul` (top scores 95/90):
- Musik Produktiv "Gibson Les Paul Junior" €1540 (95)
- 9× Tomassone variants (LP Custom, Junior reissues, Slash Victoria, etc.) — Tomassone dominates top10 because its names start with "GIBSON LES PAUL" → high WRatio.

`friedman` (top scores 90):
- Mostly Thomann pedals + Tomassone pedals (BE-OD, Smallbox, Mic-No-Mo, Sir Compre).
- 1 false-positive risk: `Friedman` collides with luthier vs amp brand in some cases — none observed in top10.

### 2.3 Per-site distribution after rank

| Site | fender mustang | gibson les paul | friedman |
|---|---|---|---|
| Thomann | 30 | 49 | 50 |
| Musik Produktiv | 34 | 45 | 60 |
| Gear4music | 62 | 0 | 0 |
| Andertons | 0 | 16 | 15 |
| Centro Chitarre | 54 | 67 | 4 |
| Tomassone | 7 | 29 | 8 |
| StrumentiMusicali.net | 8 | 11 | 6 |

---

## 3. Variant Behavior (no extra scrape)

Run: `backend/test_variants.py`. Logic verified via `normalize_query` only — actual scrape behavior depends on each site's own search box, which receives the **normalized** string.

| variant | example | normalized | impact on pipeline |
|---|---|---|---|
| lowercase  | `fender mustang`   | `fender mustang` | identical |
| uppercase  | `FENDER MUSTANG`   | `fender mustang` | identical |
| title      | `Fender Mustang`   | `fender mustang` | identical |
| extra ws   | `  fender  mustang  ` | `fender mustang` | identical |
| punctuation| `fender mustang!?.`| `fender mustang` | identical |
| accents    | `féndér mustàng`   | `fender mustang` | identical |
| partial    | `mustang`          | `mustang`        | DIFFERENT — broader scrape, more noise |
| typo       | `fender mustanx`   | `fender mustanx` | DIFFERENT — strict filter drops most; fuzzy fallback if <5 strict |

**Typo correction (`correct_typo`, threshold 0.75)** works against an explicit vocabulary, but it is NOT wired into `/api/search`. It is exposed at `/api/search/suggestions` only (`app.py:360`). User-facing search does not auto-correct typos — typo queries hit the live scrape verbatim.

Fuzzy scoring sample (rapidfuzz WRatio):
- `fender mustang` vs `Fender Mustang LT25` → 0.950
- `fender mustang` vs `Mustang amp combo` → 0.633
- `gibson les paul` vs `Gibson Les Paul Standard 50s` → 0.900
- `friedman` vs `Friedman BE-OD Overdrive` → 0.900

---

## 4. Issues & Recommendations

### 4.1 Bugs / fragility
1. **Selenium "no such window" crash** — observed Andertons (fender mustang) + Gear4music (gibson les paul, friedman). One retry implemented, but retry also fails sometimes. Root cause: parallel Chrome drivers sharing window state or being closed by another worker. **Fix:** isolate driver per scraper (separate user-data-dir), and ensure `quit()` of one driver cannot affect siblings; verify `browser_manager.py` does not share global driver.
2. **Strict filter ignores stopwords** (`_filter_strict` uses `query.split()`, not `get_query_tokens`). For Italian phrases like "chitarra a sei corde", "a" becomes a required token → drops all results. **Fix:** use `get_query_tokens(query)` in `_filter_strict`.
3. **No `SearchHistory.user_id` DB index** — slow on large user history. **Fix:** add `db.Index('ix_searchhistory_user', 'user_id', 'timestamp')`.
4. **Andertons stat reports `stato=ok` even when scrape returned 0 due to error** — `_safe_run` swallows exception and returns `[]`, then outer code marks `stato=ok` since no future exception fires. **Fix:** propagate explicit error state from `_safe_run` to `stats`.
5. **Typo correction not used in `/api/search`** — only in suggestions endpoint. **Fix:** apply `correct_typo` against a brand/model vocabulary before scrape, OR surface a "did you mean…" hint to the UI when strict count is 0.

### 4.2 Performance
- 36–42s per query is dominated by slowest scraper. `MAX_WORKERS=2` underutilizes I/O-bound scrapers (each is mostly waiting on network/Selenium). Try `MAX_WORKERS=4–6` and benchmark.
- Cache hit rate not measured. `cache_manager.cleanup_cache` is intentionally skipped during parallel runs — verify cache is being **read** (not just written) per scraper. If reads are skipped, identical queries re-scrape every time.
- Site-level latency is the real signal — instrument per-scraper duration in `stats` (currently only `_tempo_totale`).

### 4.3 Result quality
- Top-10 for `gibson les paul` is 9× Tomassone — symptom of (a) Tomassone names start with the exact query → highest WRatio, (b) tie-breaker is price ascending. Consider per-site cap in top-N to diversify (e.g. max 3 per site in top-10).
- WRatio favors short product names: a generic "Fender Mustang" (€14.90 cable accessory?) ranked #1 over actual Mustang amps. Strict-token filter does not distinguish accessories from amps. **Fix:** add product-type/category in scraper output and weight category match into `relevance_score`.
- `_parse_price` returns `999_999.0` on parse failure → silently penalizes items with malformed price. Better: separate `unknown_price` flag and rank explicitly.

### 4.4 Diacritics / case
Robust. Lower/Upper/Title/accent/punct/extra-ws all collapse to canonical normalized form. No issue here.

---

## 5. Files produced by this run
- `backend/test_three_queries.py` — driver
- `backend/test_three_queries_report.json` — raw data (top10, stats, per-site)
- `backend/test_variants.py` — normalize/variant demo
- `report/search_test_report.md` — this report
