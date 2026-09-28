# Web page (INSTRINDER)

`GET /` from a browser serves INSTRINDER, a Google-style search page. There is
no build step and no JavaScript dependency.

| File | Role |
|------|------|
| `api/web/index.html` | page template (`string.Template`, `$placeholders` filled server-side in the visitor's language) |
| `api/web/translations.json` | 73 UI strings × 18 languages |
| `api/web/static/app.css` | design tokens and components |
| `api/web/static/app.js` | state machine, SSE client, components (~10 KB gzip) |
| `api/web/static/demo.js` | fake event streams for development (loaded only in demo mode) |
| `api/web/static/fonts/` | Google Sans Flex, self-hosted (SIL OFL), latin + latin-ext |
| `api/web/static/favicon.svg` | site icon |
| `api/i18n.py` | language choice (see below) |
| `api/main.py` (`root`) | renders the template; JSON for API clients |

## Layout

- **Home** (`body[data-view=home]`): logo, one search bar, chips for the real
  search scopes (area: anywhere / Europe / USA / Asia, "major shops only" =
  `priority=1`), tagline, footer with service status and version.
- **Results** (`data-view=results`): sticky header (logo, bar, Contact, language,
  theme), area tabs with counts (client-side filter), status line with the sort
  menu, phase panel, results list, "More results" (next 20 from data already
  received). Right column (≥ 1200 px): **deals** (discounted items, card with
  product photo, shop, price, struck previous price, link to the retailer) and
  the search summary. Below 1200 px the deals become a horizontal strip after
  the list (never above it, so nothing moves while loading).

A shared `?q=…&area=…&priority=1&sort=…` link renders the results layout from
the first paint; back/forward work (`history.pushState`).

## Search lifecycle

`app.js` treats a search as a state machine:
`idle → submitting → loading → streaming → done | partial | empty | error | cancelled`.

- It reads `GET /search/stream` (Server-Sent Events, parsed from `fetch` so an
  `AbortController` can stop it): `phase`, `start`, `site`, `done`, `error`
  events. See [API](API.md#get-searchstream).
- Nothing shows under 150 ms; once shown, indicators stay at least 400 ms.
- From 150 ms: progress bar (indeterminate, then determinate with the real share
  of shops answered; a thicker wavy bar after 5 s), skeleton rows, the phase
  panel ("Preparing the search → Visiting N shops → Keeping relevant offers →
  Sorting by price") with shop icons appearing as each shop answers.
- Relevant offers stream into the list as shops answer (first 24); at `done`
  the list is replaced by the ranked one and the phase panel collapses into
  "Done · 4 steps · 12.3 s".
- Stop button or Esc cancels (closing the stream stops shops not started yet);
  a new search cancels the running one.
- Partial (some shops failed) and error states show a banner with Retry;
  results already received stay.

Layout-shift care: skeletons have result size; the phase panel collapses in
the same frame the list is swapped; the shop-icon row is one fixed-height
scrolling line; deals never sit above the list. Measured CLS ≈ 0.005.

## Contact

"Contact" in the header opens a native `<dialog>` form (name, e-mail, message,
hidden honeypot). It posts to `POST /contact`; the recipient address is server
configuration only and never appears in the page. See [API](API.md#post-contact)
and [CONFIGURATION](CONFIGURATION.md#contact-form).

## Languages (`api/i18n.py`)

Order of precedence: `?lang=` (remembered in a cookie) → the visitor's country
(CDN header `CF-IPCountry` / CloudFront / Vercel / App Engine, else the client IP
through the offline DB-IP Lite file) mapped to the languages spoken there (CLDR
via Babel; the browser's `Accept-Language` picks among them) → `Accept-Language`
→ English. 18 languages; Arabic and Urdu render right-to-left. To add one, add a
block with the same keys to `translations.json`.

## Design tokens

Custom properties on `:root`, dark theme via `prefers-color-scheme` and a manual
toggle (`data-theme`). Accent: gunmetal `#2c3539` (focus, progress, loaders;
lightened in dark mode); actions: GT orange `#ff6b1a`. Motion tokens `--dur-*`
and easings (`--ease-spring` is a `linear()` spring); only `transform`,
`opacity`, `clip-path` are animated. `prefers-reduced-motion` turns loaders
into fading dots and transitions into ≤ 150 ms crossfades.

## Accessibility

`aria-live` announcements (searching, result count, errors), `aria-busy` on
results, visible focus rings, keyboard use throughout (`/` focuses the bar,
↑/↓ in suggestions, Esc), WCAG AA contrast in both themes, 44 px touch targets
on mobile. Lighthouse: Performance 99, Accessibility 100.

## Demo mode (development only)

On localhost only: `/?demo=fast|slow|empty|error|partial` (optionally with
`&q=…`) replays fake event streams with realistic timing, so every state can be
checked without scraping. Elsewhere the parameter is ignored.

## Shop icons

`GET /favicon/{site_key}` serves each shop's icon from our origin: fetched once
server-side, cached in `data/cache/favicons/`, a letter badge when the shop has
none. Visitors never contact the shops' domains for icons. Deal photos are
loaded from the shops' image CDNs with `referrerpolicy="no-referrer"`.
