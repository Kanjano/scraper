# Infrastructure and operations

How to run INSTRINDER in production: requirements, deployment, reverse proxy,
security, scaling, observability and maintenance.

## Runtime profile

| Aspect | Value |
|--------|-------|
| Processes | **one** Python process (Uvicorn serving FastAPI) — web page, API, SSE and scheduler |
| Port | `API_PORT` (default 8000), plain HTTP; TLS terminates at the reverse proxy |
| Inbound | browsers and API clients; long-lived SSE connections (1–5 min per search) |
| Outbound | HTTPS to ~76 shop sites and their search APIs, SMTP (contact form), Hugging Face once (model download), DB-IP monthly (GeoIP file, manual) |
| Child processes | headless Chromium / Google Chrome, one per rendered search (8 shops need it) |
| Disk | image ≈ 4.5 GB (measured, arm64: Python deps, Playwright and patchright Chromium builds with system libraries, search model 240 MB; amd64 adds Google Chrome); `data/` a few MB (SQLite, favicon cache, reports, GeoIP ≈ 8 MB) |
| Database | SQLite by default (`data/instruments.db`); PostgreSQL via `DATABASE_URL` |

### Sizing

| Resource | Minimum | Recommended | Why |
|----------|---------|-------------|-----|
| vCPU | 2 | 4 | Chromium renders, embedding of product words, JSON parsing |
| RAM | 2 GB | 4 GB | each headless Chromium ≈ 150–300 MB; search model ≈ 300 MB resident; Python ≈ 200 MB |
| `/dev/shm` | 1 GB | 1 GB | Chromium crashes with Docker's 64 MB default (`shm_size` in compose) |
| Disk | 8 GB | 15 GB | image (≈ 4.5 GB) + build cache + logs |
| Network | stable outbound; a residential or EU/US exit IP matters | | several shops answer only from some regions or block datacentre IPs |

Search time is dominated by per-shop politeness (≥ 10 s between requests to one
shop) and the slowest shops, not by CPU: 15 s – 3 min for all shops. The server's
location changes which shops answer (7 shops are unreachable from outside their
region; see [STATUS](STATUS.md)).

## Deployment options

### 1. Docker (recommended)

The image (`Dockerfile`) is multi-arch:

- **amd64**: Google Chrome stable is installed; `stealth` shops use it.
- **arm64** (Graviton, Ampere, Apple silicon): no Linux Chrome exists; `stealth`
  shops automatically fall back to patchright's bundled Chromium (logged as a
  warning on each use). Set `STEALTH_BROWSER_CHANNEL=` (empty) to skip the
  attempt. Verified on arm64: Strumenti Musicali .net's JS challenge is passed
  with the bundled Chromium.

It runs as a non-root user (`uid 10001`), bakes the search model into
`/opt/models` (containers start offline and ready), and declares a
`HEALTHCHECK` on `/admin/health-check`.

```bash
cp .env.example .env            # fill in (see CONFIGURATION)
docker compose up -d --build    # builds and starts; data/ is mounted as a volume
docker compose logs -f          # JSON logs on stdout
```

Plain Docker:

```bash
docker build -t instrinder .
docker run -d --name instrinder -p 8000:8000 --shm-size=1g \
  --env-file .env -v "$PWD/data:/app/data" --restart unless-stopped instrinder
```

Build for another architecture: `docker buildx build --platform linux/amd64 -t instrinder .`

### 2. Virtual machine without Docker

```bash
sudo apt install python3.12 python3.12-venv
python3.12 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
playwright install --with-deps chromium
patchright install chromium
# amd64 only, for the best stealth disguise:
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo apt install ./google-chrome-stable_current_amd64.deb
cp .env.example .env && python main.py
```

systemd unit (`/etc/systemd/system/instrinder.service`):

```ini
[Unit]
Description=INSTRINDER
After=network-online.target

[Service]
User=instrinder
WorkingDirectory=/opt/instrinder
EnvironmentFile=/opt/instrinder/.env
ExecStart=/opt/instrinder/.venv/bin/python main.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### 3. Platforms-as-a-service

Workable only if the platform allows: long-lived HTTP responses (SSE, several
minutes), running Chromium (≥ 1 GB `/dev/shm`), ≥ 2 GB RAM, and outbound
traffic to arbitrary hosts. Serverless functions (short timeouts, no browser)
are not suitable.

## Reverse proxy

Put nginx, Caddy or a CDN in front for TLS, compression and access control.
**SSE needs buffering off and a long read timeout**, otherwise progress arrives
in one block at the end, or the connection is cut mid-search.

nginx:

```nginx
server {
    listen 443 ssl http2;
    server_name instrinder.example.com;
    # ssl_certificate … (e.g. certbot)

    location /search/stream {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_buffering off;            # the app also sends X-Accel-Buffering: no
        proxy_cache off;
        proxy_read_timeout 600s;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    location /admin/ {                  # unauthenticated in the app: restrict here
        allow 10.0.0.0/8;               # your office / VPN
        deny all;
        proxy_pass http://127.0.0.1:8000;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        gzip on;
        gzip_types text/css application/javascript application/json;
    }
}
```

Caddy:

```caddy
instrinder.example.com {
    @admin path /admin/*
    handle @admin {
        remote_ip 10.0.0.0/8
        reverse_proxy 127.0.0.1:8000
    }
    reverse_proxy 127.0.0.1:8000 {
        flush_interval -1            # stream SSE immediately
        transport http { read_timeout 10m }
    }
}
```

**Cloudflare** in front: the page language uses its `CF-IPCountry` header
directly (no GeoIP file needed). Cloudflare buffers nothing for
`text/event-stream`, but its 100 s idle timeout is covered by the app's 15 s
keep-alive comments.

**Client IP**: `api/i18n.py` and the contact rate limit read the first
`X-Forwarded-For` hop. Behind a trusted proxy that is correct; exposed
directly, a client can spoof it (only the page language and its own rate-limit
bucket are affected). Do not expose port 8000 publicly.

## Security checklist

| Topic | State | Action |
|-------|-------|--------|
| `/admin/*` endpoints | **no authentication**; `POST /admin/force-scrape` and `/admin/sync-sites` trigger work | restrict at the proxy (above) or keep the app on a private network |
| `/docs`, `/redoc`, `/openapi.json` | public | restrict at the proxy if the API is not meant to be public |
| Secrets | only in `.env` (git-ignored, excluded from the image by `.dockerignore`) | use the platform's secret store in production; `chmod 600 .env` |
| Contact form | honeypot, per-IP limit (3 / 10 min), length limits, header-injection-safe addresses | add a CAPTCHA only if abuse appears |
| XSS | page strings HTML-escaped server-side; all dynamic content inserted with `textContent` | — |
| SSRF | `/favicon/{key}` only fetches URLs of configured shops (unknown keys → 404) | — |
| Third-party requests from visitors | none, except deal photos from shops' image CDNs (sent with `no-referrer`) | proxy images too if strict privacy is required |
| Container | non-root user, no build tools at runtime | — |
| Scraping etiquette | robots.txt honoured, ≥ 10 s per domain, identifiable UA (`SCRAPER_CONTACT`) | keep the contact current |

More in [SECURITY](SECURITY.md).

## Scaling

In-process state assumes **one application process**:

- per-shop rate limiter (politeness), Shopify catalogue cache, embedding cache,
  contact rate limit, APScheduler jobs.

Running several Uvicorn workers or replicas would multiply the request rate to
each shop, duplicate scheduled jobs and split caches. To scale:

1. **Vertically first**: more CPU/RAM; raise `ScraperOrchestrator(max_workers)`
   in `api/routes/search.py` (default 5) — the largest lever on search time.
2. **Horizontally** only after moving shared state out of the process: Redis for
   cache and rate limits, the scheduler in a single dedicated instance
   (`SCHEDULER_ENABLED=False` on the others), sticky nothing (SSE is
   per-request).
3. **Result caching** of whole searches (same query within minutes) is the next
   cheap win; not implemented.

## Observability

| Signal | Where |
|--------|-------|
| Logs | JSON lines on stdout (`python-json-logger`): time, level, logger (`scraper.<shop>`, `api.*`), message; level via `LOG_LEVEL` |
| Liveness | `GET /admin/health-check` → `{"status": "ok"}` (Docker `HEALTHCHECK`, uptime monitors) |
| Shop reachability | `GET /admin/health-check/sites`; scheduled every 6 h |
| Coverage | `GET /admin/coverage` — readable shops and blocking reasons |
| Per-shop scrape status | `GET /admin/sites-status` (joined with the `sites` table) |
| Live test | `python -m scripts.test_all_stores` → `data/store_test_report.json` |
| Metrics | `monitoring/metrics.py` defines Prometheus counters/histograms, **not yet recorded nor exposed** — add a `/metrics` route (`prometheus_client.make_asgi_app`) and increments in the orchestrator to use them |

Useful log queries: `"site .* failed"` (a shop raised), `"attempt 3/3 failed"`
(a shop exhausted retries), `"contact mail not sent"` (SMTP problem),
`"semantic matching off"` (model unavailable).

## Scheduled work

With `SCHEDULER_ENABLED=True` (default) the process runs:

| Job | Interval |
|-----|----------|
| `sync_sites` (dataset → `sites` table) | once at start |
| `scrape_priority(1)` global majors | every 4 h |
| `scrape_priority(2)` broad catalogues | every 12 h |
| `scrape_priority(3)` niche shops | every 24 h |
| `health_check_all_sites` | every 6 h |

These sweeps add traffic to the shops; disable them in development and on any
secondary instance.

## Maintenance calendar

| When | Task |
|------|------|
| Monthly | refresh the GeoIP file (`data/dbip-country-lite.mmdb`, command in [CONFIGURATION](CONFIGURATION.md)) |
| Monthly | `python -m scripts.test_all_stores`; fix or disable failing shops |
| Quarterly | `python -m scripts.probe_stores` (shops change platforms and search pages); review `data/store_probe.json` |
| On Chrome / Playwright updates | rebuild the image; run the live test |
| On dependency advisories | bump pinned versions in `requirements.txt`, run `pytest` and the live test |

## Backups

`data/` holds everything stateful: the SQLite database (price history, site
status), the favicon cache (re-creatable), the GeoIP file (re-downloadable) and
test reports. Back up the database (or use PostgreSQL with its own backups) and
`.env` (through your secret store).

## Upgrade procedure

```bash
git pull
docker compose build && docker compose up -d     # or: pip install -r requirements.txt && restart
python -m scripts.test_all_stores --only thomann,reverb,sweetwater   # quick smoke
```

The database schema is created by `init_db()` (no Alembic migrations wired):
when models gain columns, add a migration or recreate the SQLite file in
non-production environments.
