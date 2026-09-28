# Functional specification

What INSTRINDER does, for whom, and the rules behind every number it shows.
Technical details: [ARCHITECTURE](ARCHITECTURE.md) · [SEARCH](SEARCH.md);
visual behaviour: [DESIGN](DESIGN.md).

## Purpose

Find a musical instrument, part or accessory across music shops worldwide and
compare prices in one currency — including shops in other languages and shops
that are hard to query automatically — so a buyer or a reseller sees the real
market price and the real deals in one place.

## Actors

| Actor | Goal |
|-------|------|
| **Visitor** | search, compare, sort, filter, open the product at the shop, write to the owner |
| **API client** | the same data as JSON (`/search`, `/search/stream`) and store coverage |
| **Operator** | configure, deploy, keep shop routes working, read messages ([GUIDA](GUIDA.md), [INFRASTRUCTURE](INFRASTRUCTURE.md)) |
| **Shops** (external) | answer searches; their robots.txt and rate limits are respected |

## Scope

- **Dataset**: 120 internationally known shops (Europe 37, USA 63, Asia 20); 76
  are searchable; the other 44 are documented with a reason (no public prices,
  unreachable, robots.txt, interactive anti-bot, search not machine-readable).
- **Out of scope**: accounts, checkout, stock reservation, price alerts, persistent
  price history in the UI (the database model exists; see [STATUS](STATUS.md)).

## Features and acceptance criteria

### F1 — Search

- The visitor types free text (brand, model, instrument, part) in any language
  and presses Enter (or a recent search).
- Optional scope before searching: area (Europe / USA / Asia) and "major shops
  only".
- **Accepted when**: every searchable shop in scope is queried; results appear
  while shops answer; the final list contains only offers whose name or brand
  matches **every** meaningful word typed (literally, as a prefix such as
  "strat" ↔ "Stratocaster", or with the same meaning in another language such as
  "violino" ↔ "violin"); function words ("per", "for", "mit"…) are not required.

### F2 — Multilingual queries

- A non-English query is also sent in English (local glossary + model), because
  shops search their catalogue in their own language.
- **Accepted when**: "chitarra elettrica fender" returns English-language shops'
  electric guitars; the English form is shown in the search phases
  ("Also in English: «guitar electric fender»") and returned by the API as
  `translated_query`; brand and model names are never altered.

### F3 — Live progress

- **Accepted when**: within 150 ms of a search that is not instantaneous the page
  shows progress; phases reflect the server's real state (prepare → visit N
  shops → keep relevant offers → sort); each shop appears when it answers, with
  errors marked; progress percentage = shops answered / shops queried; the
  visitor can stop at any time and keeps what arrived; a new search cancels the
  running one.

### F4 — Results

Each result shows: shop (icon, name, link breadcrumb), product name (link to
the shop's product page), **price in euro**, the shop's price and currency when
not euro, country, and when applicable the previous price struck through with
a "−N %" badge and an "Accessory" tag.

- **Accepted when**: prices are converted with current rates; the lowest price
  and the market average in the summary ignore accessories; duplicates (same
  shop, same product, same price) appear once.

### F5 — Sorting and filtering

| Control | Behaviour |
|---------|-----------|
| Sort: **Relevance** (default) | items before accessories; best fit to the query first (exact words, concise names, word order, early match); ties by price |
| Sort: **Price ascending / descending** | items before accessories, by price in euro |
| Sort: **Name (A–Z)** | alphabetical in the page language, numbers in natural order |
| Tabs: All / Europe / USA / Asia | filter the results already received, with counts |
| More results | next 20 of the current list |

- **Accepted when**: changing sort or tab reorders instantly without a new
  search; sort is kept in the URL (`&sort=`), so a shared link opens the same
  view.

### F6 — Deals

- The right column (a strip under the results on narrow screens) shows up to 8
  discounted items, biggest discount first, as cards with the product photo,
  shop, price and previous price; a card opens the product on the retailer's
  site in a new tab.
- **Rules**: a discount exists only when the shop states a previous price
  1–90 % above the current one; accessories are excluded; offers from a shop that
  shows a cut on ≥ 80 % of what it returned (at least 5 offers) are list prices,
  not deals, and are excluded (the struck price still shows in the result).
- **Accepted when**: no accessory and no list-price "discount" appears among
  deals; each card links to the retailer.

### F7 — Accessories

- Parts and accessories that the query did not ask for are tagged and listed
  after the items: things made *for* the searched item ("rosin for violin",
  "pece per violino"), and names whose main part is a part word (pickup, case,
  strings, sheet music…) priced well below the typical match, or priced trivially
  low.
- **Accepted when**: searching "fender stratocaster" lists guitars first and
  pickup sets after; searching "fender stratocaster pickup" treats pickups as
  items.

### F8 — Sharing and history

- The address bar holds query, area, "major shops" and sort; back/forward
  restore previous searches; the last 8 queries are suggested (stored only in
  the visitor's browser, removable one by one).

### F9 — Language and theme

- The page language follows the visitor's country (18 languages, right-to-left
  where needed), overridable from the header and remembered; light/dark theme
  follows the system and can be toggled.

### F10 — Contact

- "Contact" opens a form (name, e-mail, message). The message is e-mailed to the
  owner; the visitor's address is set as reply-to.
- **Rules**: the recipient address is server configuration and never appears
  in the page; at most 3 messages per 10 minutes per visitor IP; name ≤ 100
  characters, message 10–5000; bots filling a hidden field are silently ignored.
- **Accepted when**: a valid message is delivered and confirmed ("Message
  sent"); an unconfigured server answers "not available" instead of losing it;
  floods get "too many messages".

### F11 — API

- `GET /search` returns the ranked result set; `GET /search/stream` the same as
  live events; `GET /stores` and `GET /admin/coverage` describe the dataset and
  why shops are not readable. Full reference: [API](API.md).

## Business rules — summary

| Rule | Value |
|------|-------|
| Currency | all comparisons in EUR, live rates with a static fallback; Shopify prices in the currency the shop actually served |
| Relevance | every meaningful query word must match; cross-language matches need similarity ≥ 0.85 |
| Translation | glossary first; model only at similarity ≥ 0.93; brands unchanged |
| Accessory | "for …" pattern, or part word + price < 30 % of the typical match, or price < 5 % of it |
| Discount | 1–90 % below the stated previous price; list-price shops (≥ 80 % discounted, ≥ 5 offers) excluded from deals |
| Lowest price / average | items only (accessories excluded) |
| Politeness | ≥ 10 s between requests to one shop; robots.txt honoured |

## Error and edge cases

| Situation | Behaviour |
|-----------|-----------|
| A shop does not answer | the search continues; the shop is marked in the phase panel; a "N shops did not answer" banner with Retry |
| The whole search fails | error banner with Retry; results already received stay |
| Nothing matches | "No results for «…»" with three suggestions; focus back in the bar |
| Visitor stops | "Search stopped"; received results stay |
| Query in an unsupported script | matched literally/as substring (CJK) |
| Shop page changes | the shop returns nothing or is caught by the live test; see maintenance in [GUIDA](GUIDA.md) |
