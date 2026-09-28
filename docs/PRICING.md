# Pricing & Market Analysis

## PricingEngine (`pricing/pricing_engine.py`)

`calculate_suggested_price(offers)` derives a competitive price from multiple
offers. Each offer is a dict: `{site, price_eur, reviews, stock}` (`price_eur`
required). All inputs are assumed already normalized to EUR.

### Algorithm

1. **Filter** to offers that have a price (`price_eur`). If none → `{"error": ...}`.
2. **Stats** — compute `min`, `mean` (market average), and `median`.
3. **Anchor** — drop high outliers (price > 2× median) for robustness, then take
   the lowest remaining price as the anchor.
4. **Discount** — start from a base, then add bonuses:
   - base **7%** (from `PRICE_DISCOUNT_MULTIPLIER = 0.93`)
   - **+3%** if a bestseller exists (offer with `reviews > 500`)
   - **+2%** if high stock (offer with `stock > 20`)
   - capped at **`MARGIN_MAX_PERCENT`** (default 15%)
5. **Suggested price** = `anchor × (1 − discount)`.
6. Return suggested price, margin %/amount, lowest site + price, market average,
   number of sites analyzed, and a human-readable `reasoning` string.

### Worked example

Offers: A=100 (10 rev, 5 stk), B=110 (600 rev, 30 stk), C=120 (5 rev, 2 stk).

- market average = 110, median = 110, anchor = 100 (no high outliers)
- bestseller present (B, 600 rev) → +3%; high stock present (B, 30) → +2%
- discount = 7 + 3 + 2 = **12%** (≤ 15 cap)
- suggested = 100 × 0.88 = **88.00**, margin = 12.00 (12%)

This is covered by `tests/test_pricing.py`.

### Configuration knobs

| Setting | Effect |
|---------|--------|
| `PRICE_DISCOUNT_MULTIPLIER` | base discount (`1 − multiplier`) |
| `MARGIN_MAX_PERCENT` | hard cap on total discount |
| `MARGIN_MIN_PERCENT` | lower bound (reserved for future margin-floor logic) |

> Note on outliers: only **high** outliers (> 2× median) are removed. An
> abnormally low price still becomes the anchor — intended (we anchor to the
> lowest credible market price), but worth knowing when feeding noisy data.

## MarketAnalyzer (`pricing/market_analyzer.py`)

Operates on persisted data via a SQLAlchemy session.

- `market_overview()` — groups `Instrument` rows by category; returns per-category
  count and average EUR price, total instrument count, and an overall average.
  Backs `GET /market-analysis`.
- `price_trend(instrument_id, days=30)` — reads `PriceHistory` within the window,
  returns ordered `(date, price_eur)` points and a simple `up` / `down` / `flat`
  trend from first vs. last point. Backs `GET /price-history/{id}`.

Both return empty/zeroed results until live scrapes are persisted to the
database (see [STATUS](STATUS.md)).
