# Changelog

## 0.2.0 — 2026-09-28 — INSTRINDER

### Added
- **INSTRINDER web page**: search-engine layout, live progress over
  Server-Sent Events (`/search/stream`), phases and shops answering in real
  time, stop/cancel, shareable URLs, recent searches, light/dark theme,
  18 languages chosen by the visitor's country (right-to-left included),
  demo mode for development.
- **Sorting**: relevance (new per-offer score), price ascending/descending, name.
- **Deals column**: discounted items with product photo, shop, previous price
  and a link to the retailer; list-price "discounts" filtered out.
- **Discounts and images** read from every source that has them (Shopify,
  WooCommerce, Algolia, Doofinder, Constructor, Reverb, schema.org, embedded
  JSON, struck-through prices, selectors).
- **Contact form** (`POST /contact`) over SMTP; recipient only in `.env`.
- **Search intelligence, all local**: relevance filter with a multilingual
  embedding model, query translation (gear glossary + model), accessory
  detection, relevance score.
- **Anti-bot routes**: public search APIs (Algolia, Doofinder, Constructor),
  Chrome TLS fingerprint (curl_cffi), real Chrome (patchright) with Chromium
  fallback on arm64.
- **Shop icons** served from our origin (`/favicon/{site_key}`).
- Shopify catalogues over 1000 products completed through collections; POST
  search forms (`search_post`).
- Docker image: multi-arch, non-root, model baked in, health check.
- Documentation: architecture, infrastructure, design system, functional
  specification, search, testing, security, user guide (Italian).

### Fixed
- Instalment prices read as product prices; prices split across elements;
  prices without currency sign (Music & Arts).
- Routes that ignored the query (homepage grids); a per-shop audit fixed 13
  shops and disabled 3 whose search is not machine-readable.

### Changed
- Coverage: 76 of 120 shops, each verified to search what is typed.
- Scraper contact moved from code to `SCRAPER_CONTACT`.

## 0.1.0 — 2026-06

- Initial API: 120-shop dataset, route probe, Shopify/WooCommerce/Reverb/
  schema.org/grid scrapers, EUR normalisation, suggested price, scheduler.
