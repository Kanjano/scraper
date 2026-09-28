# Anti-Bot Strategies & Proxy Support

## Strategy tiers (cheapest first)

1. **Official or public search API** — no HTML, no bot wall. Reverb
   (`api.reverb.com`); Sweetwater and Perfect Circuit through the Algolia index
   their own search box queries (`AlgoliaScraper`, public search-only key);
   Gear4music through its Doofinder search engine (`DoofinderScraper`).
2. **Static HTML** — plain `requests` + parsing (Thomann, `StructuredScraper`).
3. **Chrome TLS fingerprint** — `impersonate: true` in a store override makes
   `BaseScraper` use a `curl_cffi` session that reproduces Chrome's TLS/HTTP2
   handshake and headers. Clears edge bot scoring that rejects Python clients
   (HTTP 403/406). Used for Bax Music, Scan, Guitar Salon, Vintage Instruments,
   and for the Algolia key fetch on Perfect Circuit. Same speed as `requests`.
4. **Real Chrome** — `stealth: true` on a `playwright` store renders through
   patchright (Playwright without the CDP automation leaks) driving the
   installed Google Chrome, with `HeadlessChrome` removed from the UA. Clears
   Cloudflare's non-interactive JS challenge and PerimeterX. Used for B&H and
   Strumenti Musicali .net. ~5–10 s per search. Needs Google Chrome on the host.
5. **Residential proxies / commercial unlockers** — for interactive challenges
   (Cloudflare Turnstile checkbox, Akamai press-and-hold). Proxy rotation is
   built in; unlocker APIs (Zyte / ScrapingBee / Bright Data) are the paid fallback.

Captchas are not solved and robots.txt is still honoured.

## Findings per protected site (2026-09)

| Site | Protection | Route |
|------|-----------|-------|
| Sweetwater | PerimeterX on search | Algolia API (static public key) |
| Perfect Circuit | Cloudflare on search | Algolia API (secured key read from homepage) |
| Gear4music | Cloudflare on search, Doofinder overlay | Doofinder API |
| Bax Music | HTTP 406 to non-browser TLS | `impersonate` + selectors |
| Scan Pro Audio | HTTP 403 to non-browser TLS | `impersonate` + selectors |
| Guitar Salon | HTTP 403 to non-browser TLS; currency by IP | `impersonate` + `session_setup` (USD) |
| Vintage Instruments | HTTP 403 to non-browser TLS | `impersonate` + WooCommerce Store API |
| B&H | Cloudflare JS challenge | `stealth` Chrome + selectors |
| Strumenti Musicali .net | HTTP 428 JS challenge | `stealth` Chrome + selectors |
| Guitar Center | Akamai press-and-hold on search | blocked: proxy/unlocker |
| The Ukulele Site, Full Compass | Cloudflare Turnstile (interactive) | blocked: proxy/unlocker |

## Proxy support (`utils/proxy_manager.py`)

`ProxyManager` is a thread-safe round-robin pool.

### Configuration

```env
USE_PROXY=True
PROXY_LIST=user:pass@host1:8080, host2:3128, socks5://10.0.0.1:1080
```

Accepted entry formats (scheme defaults to `http`):

- `host:port`
- `user:pass@host:port`
- `http://user:pass@host:port`
- `socks5://host:port`

If `USE_PROXY=True` but `PROXY_LIST` is empty, proxies auto-disable with a warning.

### API

| Method | Returns |
|--------|---------|
| `active` | bool — enabled and at least one proxy |
| `next_proxy()` | next proxy URL (round-robin) or `None` |
| `as_requests(url=None)` | `{"http": url, "https": url}` for `requests` |
| `as_playwright(url)` (static) | `{"server", "username", "password"}` for Playwright |

### Wiring

- **requests path** — `BaseScraper.respectful_request` calls
  `proxy_manager.as_requests()` and passes `proxies=` to `requests` (rotates per
  request). A per-call `proxies=` override is honored.
- **Playwright path** — `PlaywrightScraper._render_html` converts the next proxy
  via `as_playwright()` and passes it to `chromium.launch(proxy=...)`, logging the
  server used.

### Tests

`tests/test_proxy.py` covers: disabled returns `None`; enabled-but-empty
auto-disables; round-robin wraparound; scheme defaulting; `requests` shape;
Playwright shape with and without auth; `None` handling. (7 tests.)

### Status

Plumbing is complete and unit-tested, but **not exercised against a live proxy**
(none configured). To use: add real residential proxies to `PROXY_LIST`, set
`USE_PROXY=True`, and retry the Cloudflare-protected sites. Proxy rotation alone
may not clear a full Cloudflare JS challenge — pair it with `PlaywrightScraper`
(already proxy-aware) or an unlocker API.
