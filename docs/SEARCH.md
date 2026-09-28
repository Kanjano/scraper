# Search: relevance, translation, accessories, deals, sorting

A search fans out to every readable shop (see [SCRAPERS](SCRAPERS.md)); this
page describes what happens to the offers that come back, in the order the
code applies it. Everything runs locally: no external AI service, no tokens.

```
query ──► query_translation.to_english ──► each shop: original (+ English) query
                                                    │
offers ◄── validator.normalize (EUR, discount) ◄────┘
   │
   ├─► relevance.filter_relevant   drop offers that do not match the words typed
   ├─► dedupe (shop, url|name, price)
   ├─► relevance.flag_accessories  parts/accessories the query did not ask for
   ├─► relevance.score             0..1 fit, for "sort by relevance"
   └─► aggregate: accessories last, lowest price / market average from items only
```

Code: `scheduler/orchestrator.py` (`search_all_sites`, `aggregate_results`),
`scrapers/relevance.py`, `scrapers/query_translation.py`, `scrapers/validator.py`.

## 1. Query translation (`scrapers/query_translation.py`)

Shops search their own catalogue in their own language, so "chitarra elettrica
fender" finds nothing at Sweetwater. `to_english(query)` returns the English
version, or `None` when the query already is English; the orchestrator then
sends **both** queries to every shop and keeps offers that match either.

1. **Glossary first** — `scrapers/data/gear_glossary.json`: 49 gear concepts in
   ~13 languages (it, es, fr, de, pt, nl, tr, ru, ja, zh, ko, id, hi), phrases
   included ("flauto dolce" → recorder, エレキギター → electric guitar).
2. **Embedding model second**, only for words the glossary does not know, onto
   the English gear vocabulary (`scrapers/data/gear_vocabulary.txt`), and only
   when the similarity is ≥ 0.93. Word embeddings alone were measured to be
   unreliable ("batteria" is closer to a battery than to drums; "Verstärker"
   scored 0.90 against *tuner*), hence the glossary.
3. **Everything else passes through** — brands and models are the same in every
   language (Fender, Stratocaster, 1959).

Extend the glossary to improve a language: add words to the English concept's
list. The API returns the translation as `translated_query`.

## 2. Relevance filter (`relevance.filter_relevant`)

Shop search engines are loose (any word, fuzzy, "popular items" when nothing
matches) and some pages carry unrelated products, so every offer is checked
again, whichever scraper produced it. **Every word of the query must appear in
the offer's name or brand**, where a word matches:

- literally, or as a prefix in either direction when ≥ 4 letters
  ("strat" ↔ "Stratocaster");
- as a substring for non-Latin scripts (CJK has no spaces);
- **by meaning in another language**: a local multilingual embedding model
  (`paraphrase-multilingual-MiniLM-L12-v2`, ONNX via fastembed, ~240 MB,
  downloaded once into `data/models/`, then offline) accepts a name word with
  cosine similarity ≥ 0.85 ("violino" ↔ "violin", "chitarra" ↔ "Gitarre").

Function words ("per", "for", "mit", "de"…) are never required. Text is
compared lowercase without Latin accents; marks on other scripts are kept
(フェンダー stays フェンダー). With `SEMANTIC_MODEL=` empty the filter is
purely literal.

Why not semantic search alone: measured on real results, a whole-name
similarity ranks "Fender **Telecaster** Custom Shop" (0.68) above a genuine
"1960 Journeyman Relic **Stratocaster**" (0.30) for "fender stratocaster custom
shop" — model names must match literally.

## 3. Accessories (`relevance.flag_accessories`)

Offers stay in the results but are flagged `is_accessory`, ranked after the
items, and excluded from the lowest price and the market average when:

- **made "for" the searched item** — the query's words appear only after
  *for / per / für / pour / para / voor* ("Rosin for violin", "Pece per violino",
  "Christmas Carols for Violin"), whatever the price; or
- **a part word heads the name** (pickup, case, strings, cable, sheet music
  markers like *op.*, *KV*, *concerto*…) **and** the price is under 30 % of the
  median of the matches without part words; words after *with / w/ / con / mit*
  are features, not the product ("Stratocaster w/ case"), and "6 String" is a
  description; or
- **the price is trivial** — under 5 % of that median, with or without a part
  word.

The ratios are deliberate, fixed heuristics (`_CHEAP`, `_TRIVIAL`). A semantic
classifier ("violin" vs "accessory for violin") was tested and was right about
half the time with this model, so it is not used.

## 4. Relevance score (`relevance.score`)

For "sort by relevance", each offer gets a 0..1 score (best of the original
and English query):

| Signal | Weight |
|--------|--------|
| query words found **exactly** (not only by prefix/meaning) | 0.45 |
| brevity: query words / name words | 0.25 |
| query words in the query's order | 0.15 |
| early match (first matching word near the start) | 0.15 |

Accessories are halved.

## 5. Prices, discounts and deals

`scrapers/validator.normalize` converts to EUR (`price_eur_equivalent`) and,
when a scraper found the price before the discount (`original_price`), computes
`discount_pct` — only for a plausible 1–90 % cut, otherwise the pre-sale price
is dropped as a misreading. Sources of `original_price`:

| Source | Field |
|--------|-------|
| Shopify feed | `compare_at_price` of the cheapest variant |
| WooCommerce Store API | `prices.regular_price` |
| Algolia (Sweetwater) | `price.retailPrice` vs `price.finalPrice` |
| Doofinder (Gear4music) | `price` vs `best_price` |
| Constructor (Andertons) | `price` vs `salePrice` |
| Reverb API | `original_price` (price drops) |
| schema.org | `priceSpecification` of type StrikethroughPrice / ListPrice |
| embedded JSON | `compare_at_price`, `regular_price`, `listPrice`, `oldPrice`… |
| grid detection | struck-through price (`<s>`, `<del>`, classes like `old`, `was`, `strike`) |
| CSS selectors | `original_price` selector (Bax `span.van-prijs`, Guitar Guitar RRP…) |

Discounts are **as stated by each shop**. When a shop shows a cut on at least
80 % of the offers it returned in a search (and at least 5 offers), the cut is a
permanent list price rather than a sale: those offers get
`discount_everywhere: true`, keep their struck price, and stay out of the deals
column (`scheduler/orchestrator._flag_list_price_discounts`). The page's right
column shows the eight biggest remaining discounts among non-accessory matches,
each card linking to the retailer.

Grid-parsed prices also skip instalment offers ("$392/month", Klarna/Affirm
blocks) and re-join prices split across elements ("$" "4,699" ".99").

## 6. Sorting (page)

Client-side, over the final list (`api/web/static/app.js`, `SORTS`):

| Mode | Order |
|------|-------|
| `relevance` (default) | items before accessories, score ↓, price ↑ |
| `price_asc` | items before accessories, EUR price ↑ |
| `price_desc` | items before accessories, EUR price ↓ |
| `alpha` | name, locale-aware, numbers in natural order |

The choice is kept in the URL (`&sort=price_asc`), so it can be shared. The
API itself returns items first, then by price.

## Tests

`tests/test_relevance.py` (filter, accessories, translation),
`python -m scrapers.relevance` and `python -m scrapers.query_translation`
(self-checks), `tests/test_extractors.py` (instalments, split prices).
