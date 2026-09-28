# Security and privacy

## Threat model in brief

INSTRINDER is a public, read-only search page plus an API. It holds no user
accounts and no payment data. What matters: the owner's secrets (SMTP
credentials, contact address), abuse of the endpoints that do work (search,
contact, admin), injection through data scraped from third-party pages, the
visitors' privacy, and good conduct toward the shops.

## Secrets

- All secrets live in `.env` (`ADMIN_TOKEN`, `SMTP_PASSWORD`, `CONTACT_EMAIL`,
  `SCRAPER_CONTACT`, `REVERB_API_KEY`, `PROXY_LIST` credentials). Generate the
  admin token with `python -c "import secrets; print(secrets.token_urlsafe(32))"`
  and rotate it by changing `.env` and restarting. `.env` is
  git-ignored and excluded from the Docker build context (`.dockerignore`);
  `.env.example` contains only empty placeholders.
- The contact recipient is never sent to the browser: the form posts to
  `/contact` and the server composes the mail.
- In production prefer the platform's secret store over a file; otherwise
  `chmod 600 .env`.
- Git history: an earlier commit contained the scraper contact address in the
  User-Agent (moved to `SCRAPER_CONTACT`). Commit metadata carries the author's
  e-mail; use GitHub's no-reply address in `git config user.email` to avoid it.

## Endpoint exposure

| Endpoint | Risk | Mitigation |
|----------|------|------------|
| `GET /search`, `/search/stream` | expensive (fans out to ~76 shops) | put a rate limit per IP at the reverse proxy; consider caching identical searches |
| `POST /contact` | spam, header injection | honeypot, 3 messages / 10 min per IP, length limits, strict e-mail pattern without CR/LF, name without line breaks, `EmailMessage` headers |
| `/admin/*`, `/metrics` | `force-scrape` and `sync-sites` start work; coverage and metrics disclose internals | **admin token required** (`ADMIN_TOKEN`, constant-time check; closed with 403 when unset); optionally also an IP allow-list at the proxy |
| `/docs`, `/redoc`, `/openapi.json` | disclose the API | restrict if the API is not public |
| `/favicon/{site_key}` | server-side request forgery | fetches only the URL of a configured shop; unknown keys → 404 |
| `/static/*` | — | static files only |

## Injection

- **HTML/XSS**: the template's placeholders are HTML-escaped on the server;
  strings are embedded as JSON with `</` escaped; all scraped data (names,
  shops, URLs) is written to the page with `textContent` or attributes, never
  `innerHTML`. Product links open with `rel="noopener"` (deal cards also
  `noreferrer`).
- **E-mail headers**: visitor input reaches only `Reply-To` and the subject after
  validation that forbids line breaks.
- **Scraped content** is treated as data: parsed with BeautifulSoup/JSON, never
  evaluated.

## Privacy

- **Page language** from the visitor's country uses the CDN header or an
  **offline** GeoIP database; no IP leaves the server.
- **Shop icons** are fetched server-side and served from our origin, so visitors
  do not contact ~76 shop domains.
- **Deal photos** are loaded from the shops' image CDNs with
  `referrerpolicy="no-referrer"`; this is the only third-party request a visitor
  makes. Proxy images server-side if stricter privacy is required.
- **Search history** and theme stay in the visitor's `localStorage`; nothing is
  tracked server-side beyond standard access logs.
- **Contact messages** include the visitor's name, e-mail, message, page
  language and IP (for abuse handling); they are sent by e-mail only, not stored.
- **Search model** runs locally; queries are not sent to any AI service.

## Conduct toward shops

- robots.txt is honoured per route (e.g. Shopify's `/search` ban, Thomann's
  `/intl/`); `Music Store` and `Muziker` are excluded because their robots.txt
  forbids search.
- At least 10 s between requests to the same shop by default; one catalogue
  read per Shopify shop per 12 h.
- An identifiable User-Agent with a contact (`SCRAPER_CONTACT`).
- Edge anti-bot walls are passed only where the public data is reachable
  without solving a challenge (public search APIs, a Chrome TLS fingerprint, a
  real browser). **Captchas and interactive challenges are never solved**; those
  shops are disabled with a reason. Check each shop's terms before commercial
  use of its prices.

## Dependencies and container

- Versions are pinned in `requirements.txt`; update them on advisories and run
  the tests ([TESTING](TESTING.md)).
- The image runs as a non-root user (uid 10001) and ships no compilers.

## Reporting

Report vulnerabilities privately to the repository owner (GitHub security
advisories on the repository) rather than in public issues.
