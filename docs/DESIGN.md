# Design system

The visual and interaction design of the INSTRINDER page: principles, identity,
tokens, components, layout, motion, states, accessibility and localisation.
Implementation lives in `api/web/static/app.css` (tokens and components) and
`api/web/static/app.js` (behaviour); see [FRONTEND](FRONTEND.md) for the code
view.

## Principles

1. **Familiar first.** The layout follows the search-engine pattern everyone
   knows: one bar on the home, a list of results, tabs underneath. No learning
   curve, no brand assets of any search engine.
2. **Always say what is happening.** A search takes seconds to minutes; the page
   shows real progress — phases, shops answering, results arriving — never a
   blank screen or a fake percentage.
3. **Numbers you can trust.** Prices in euro in bold, the shop's own price and
   currency next to it, discounts only as stated by the shop, accessories
   labelled and ranked last.
4. **Restraint.** Two brand colours, one typeface, motion only on `transform`,
   `opacity` and `clip-path`, one element in focus at a time.
5. **Everyone.** WCAG AA contrast in both themes, full keyboard use, screen
   reader announcements, reduced-motion variants, 18 languages including
   right-to-left.

## Identity

| Element | Definition |
|---------|------------|
| Name | **INSTRINDER** — always upper case, one word |
| Wordmark | the name set in Google Sans Flex, weight 500, tracking −0.02 em, rounded terminals (`"ROND" 60`), one colour (text colour); always left-to-right, also on RTL pages |
| Icon | 64 × 64 rounded square (radius 16) in gunmetal, "IN" in white, a GT-orange bar underneath (`static/favicon.svg`) |
| Voice | short, plain, first person for the machine's work ("Visiting 76 shops", "Keeping relevant offers"); no jargon |

## Colour

Tokens are CSS custom properties on `:root`; the dark theme redefines them for
`prefers-color-scheme: dark` and for the manual toggle (`data-theme`).

| Token | Light | Dark | Use |
|-------|-------|------|-----|
| `--bg` | `#ffffff` | `#1b1c1e` | page background (dark is not pure black) |
| `--surface` | `#f6f7f9` | `#26272a` | footer, hover rows, skeletons |
| `--surface-2` | `#eceef1` | `#303134` | chips hover, tags |
| `--border` | `#dfe1e5` | `#3c4043` | dividers, inputs, cards |
| `--text` | `#1f1f1f` | `#e8eaed` | primary text |
| `--text-2` | `#5f6368` | `#9aa0a6` | secondary text, URLs, metadata |
| `--link` | `#1a0dab` | `#8ab4f8` | result titles |
| `--visited` | `#681da8` | `#c58af9` | visited result titles |
| `--accent` | `#2c3539` gunmetal | `#b7c4cb` | focus rings, progress bar, loaders |
| `--cta` | `#ff6b1a` GT orange | `#ff7a2e` | primary buttons, active chips, tab indicator, discount badges |
| `--on-cta` | `#141414` | `#141414` | text on orange |
| `--ok` · `--warn` · `--danger` | `#188038` · `#b06000` · `#c5221f` | `#81c995` · `#fdd663` · `#f28b82` | status dot, completed phase, partial banner, errors |

Measured contrast (WCAG 2.x):

| Pair | Light | Dark | Requirement |
|------|-------|------|-------------|
| text on bg | 16.5 : 1 | 14.2 : 1 | AA 4.5 |
| secondary text on bg | 6.1 : 1 | 6.5 : 1 | AA 4.5 |
| secondary text on surface | 5.6 : 1 | 5.7 : 1 | AA 4.5 |
| link on bg | 12.4 : 1 | 8.1 : 1 | AA 4.5 |
| visited on bg | 9.0 : 1 | 6.8 : 1 | AA 4.5 |
| accent (focus, loaders) on bg | 12.5 : 1 | 9.6 : 1 | non-text 3 : 1 |
| text on GT orange | 6.5 : 1 | 7.1 : 1 | AA 4.5 |
| success / danger on bg | 5.0 / 5.8 : 1 | 8.7 / 7.1 : 1 | AA 4.5 |

Why dark text on orange: white on `#ff6b1a` is only ~2.9 : 1; the near-black
label keeps the racing-orange buttons legible and gives them their character.

## Typography

- **Google Sans Flex** (SIL OFL), self-hosted, latin + latin-ext subsets,
  variable weight 400–700, `font-display: swap`, preloaded. A metric-matched
  fallback face (`size-adjust`, ascent/descent overrides on Arial/Helvetica/
  Roboto) avoids layout shift when it swaps in. Other scripts (CJK, Arabic,
  Devanagari, Bengali, Cyrillic…) use the platform's system fonts.

| Role | Size / line height | Weight |
|------|--------------------|--------|
| Wordmark, home | `clamp(44px, 7vw, 84px)` / 1 | 500 |
| Wordmark, header | 26 px (22 px mobile) | 500 |
| Result title | 20 / 26 px (18 / 24 mobile) | 400, link colour |
| Body, search input | 16 / 24 px | 400 |
| Snippet, UI labels | 14 / 22 px | 400; price 15 px 600 |
| Metadata, URLs, notes | 12–13 px | 400 |
| Section titles (panels, dialog) | 16–20 px | 500 |

## Space, shape, elevation

- Spacing on a 4 px base (4, 8, 12, 16, 20, 24, 28, 32…); 28 px between
  results on desktop, 12 px between cards on mobile.
- Radii: `--r-s` 8 px (buttons, chips, inputs), `--r-m` 16 px (cards, panels,
  dialog), `--r-pill` 999 px (search bar, badges); the search bar is 24 px
  when it grows to several lines.
- Elevation: none at rest. `--shadow-hover` `0 1px 6px rgb(32 33 36 / .28)` on
  hover/focus of the search bar, deal cards and menus; `--shadow-header` once
  the page scrolls.

## Motion

| Token | Value | Use |
|-------|-------|-----|
| `--dur-xs` | 100 ms | press feedback (scale 0.98–0.99) |
| `--dur-s` | 200 ms | hover, focus, fades |
| `--dur-m` | 300 ms | entrances, panel collapse, chip fill |
| `--dur-l` | 450 ms | home → results transition, theme reveal |
| `--ease-standard` | `cubic-bezier(.2,0,0,1)` | most transitions |
| `--ease-enter` | `cubic-bezier(.05,.7,.1,1)` | things appearing |
| `--ease-exit` | `cubic-bezier(.3,0,.8,.15)` | things leaving |
| `--ease-spring` | `linear(…)` spring with slight overshoot | loader morph, icon swaps |

Choreography:

- **Home → results**: same-document View Transition; wordmark and search bar
  (`view-transition-name: brand / search`) fly into the header, the rest
  fades in; without the API, a 200 ms crossfade.
- **Wordmark entrance** once per session: letters rise 8 px with a 25 ms stagger.
- **Results** enter with fade + 8 px rise, 50 ms stagger, first 8 only.
- **Theme switch**: circular reveal from the toggle button.
- Only `transform`, `opacity` and `clip-path` (plus the SVG check stroke) are
  animated — never width, height or position.

## Components

| Component | Anatomy and behaviour |
|-----------|----------------------|
| **Search bar** | pill, 48 px (44 px in the header), lens on the leading side, clear "×" (appears with the text), submit; the textarea grows up to 5 lines (`field-sizing: content`, JS fallback); Enter searches, Shift+Enter breaks lines; on submit the lens morphs into the mini loader |
| **Suggestions** | recent searches (last 8, stored locally) merged with the bar into one card; clock icon, remove "×"; ↑/↓, Enter, Esc; ARIA listbox with active descendant |
| **Chips** (home) | search scope: anywhere / Europe / USA / Asia (radio group) and "major shops only" (toggle); active state fills from the leading edge in GT orange |
| **Tabs** (results) | All / Europe / USA / Asia with counts; a 3 px orange ink slides under the active tab (transform only) |
| **Status line** | loader + "Searching… · 12 s", Stop button while busy; result count ("205 results from 17 shops · 58 s") and the Sort menu when done |
| **Phase panel** | four steps — pending dot → active loader → done check drawn in 300 ms; a single-height row of shop icons appearing as shops answer (error shops marked "!") with a counter; collapses to "Done · 4 steps · 58 s" |
| **Progress bar** | 3 px under the header: indeterminate, then determinate with the real share of shops answered, then a 6 px wave after 5 s; fills and fades at the end |
| **Shape loader** | 24 px shape morphing through 7 rounded forms while slowly rotating (border-radius keyframes, spring easing); three fading dots under reduced motion |
| **Skeleton** | result-sized placeholders (icon, two short lines, title, snippet) with a translating shimmer, 80 ms phase offset per line |
| **Result** | shop icon in a 26 px circle, shop name, breadcrumb URL, ⋮ menu (open, copy link, copy raw data); title in link colour (underlined on hover, visited colour); snippet: **price in €**, struck previous price, original price and currency, country, "−N %" badge, "Accessory" tag |
| **Deal card** | 4 : 3 photo on white (placeholder: the shop icon), "−N %" badge on the photo, shop icon and name, two-line product name, price and struck previous price; the whole card is one link to the retailer (new tab, no referrer); hover shadow, press scale |
| **Banner** | inline, for partial (warning border) and error states, with Retry in GT orange |
| **Empty state** | icon, "No results for «…»", three concrete suggestions; focus returns to the bar |
| **Contact dialog** | native `<dialog>` with backdrop; title, intro, name, e-mail, message, Close and Send; inline status (sending, sent in green, error in red) |
| **Toast** | bottom-centred, inverse colours, 1.5 s ("Copied") |

## Layout and breakpoints

| Width | Layout |
|-------|--------|
| ≥ 1200 px | header grid `148 px · 650 px · 1fr`; results in the middle column; right column (max 400 px) with **deals** (2-column card grid) and the search summary |
| 768–1199 px | same header; deals become a horizontal scroll strip **after** the results (never above them, so nothing moves while loading); summary hidden |
| < 768 px | compact header (wordmark + actions, bar below, scrollable tabs), results as bordered cards with 16 px padding, 44 px touch targets, contact as an icon |

## States and timing

The search is a state machine: `idle → submitting → loading → streaming →
done | partial | empty | error | cancelled`.

| Time | What the visitor sees |
|------|----------------------|
| 0–150 ms | only the pressed bar and the mini loader — no flash |
| ≥ 150 ms | progress bar, phase panel, 4 skeletons; once shown, indicators stay ≥ 400 ms |
| first shop | results replace skeletons one by one; shop icons pop in |
| > 5 s | wavy progress bar, elapsed seconds in the status line |
| done | ranked list replaces the streamed one in the same frame as the panel collapses; counter animates to the final number (400 ms) |

Layout stability is a design requirement: measured cumulative layout shift ≈
0.005 on real searches.

## Accessibility

- Landmarks: header, `role="search"`, main, aside; skip link to results.
- Live regions announce "Searching…", the result count, errors and "Stopped";
  results carry `aria-busy` while loading.
- Focus: 2 px accent outline with 2 px offset; logical order; dialog traps focus
  natively; Esc closes suggestions, then stops a running search.
- Keyboard: `/` focuses the bar; ↑/↓/Enter in suggestions; tabs, sort, menus,
  cards all reachable.
- Reduced motion: no shimmer, dots instead of morphing shapes, transitions
  shortened to ≤ 150 ms crossfades, no stagger.
- Lighthouse: Accessibility 100 on home and results.

## Localisation

- 18 languages chosen by the visitor's country (see [FRONTEND](FRONTEND.md)),
  switchable from the header; strings in `api/web/translations.json` (73 keys).
- Right-to-left (Arabic, Urdu): `dir="rtl"`, logical properties
  (`inset-inline-*`, `margin-inline-*`), mirrored chip fill; the wordmark stays
  left-to-right.
- Prices, numbers and country names use `Intl.NumberFormat` and
  `Intl.DisplayNames` in the page language; sorting by name uses `Intl.Collator`.

## Performance budget

| Metric | Target | Measured |
|--------|--------|----------|
| Lighthouse Performance | ≥ 90 | 99 (home and results) |
| JavaScript | < 15 KB gzip | ≈ 10 KB (`app.js`), demo code loaded only in demo mode |
| CSS | — | ≈ 8 KB gzip |
| Fonts | — | 85 KB (latin) + 40 KB (latin-ext), one family |
| Long tasks during search at 4× CPU slowdown | none > 50 ms | none |
| CLS | < 0.1 | ≈ 0.005 |
