"""Probe every store in the dataset and write the scraping overrides.

Per store: read robots.txt, fetch the homepage, learn the shop's own search
route from its search form, then try the routes in order of reliability

    1. Shopify catalogue feed  /products.json        (structured JSON)
    2. WooCommerce Store API   /wp-json/wc/store/v1  (structured JSON)
    3. the search route(s) advertised by the homepage form  (HTML)
    4. a short list of conventional search paths            (HTML)
    5. the same HTML routes rendered in Chromium, for client-side grids

HTML routes are scored with the very same parsers the scrapers use
(schema.org first, repeated-grid detection second), so a route that probes
green also works at runtime.

Writes:
  * ``config/store_overrides.json`` — what the scrapers read
  * ``data/store_probe.json``       — full report (attempts, statuses, counts)

Respects robots.txt, sends an identifiable user-agent, probes one domain at a
time per worker, and never attempts to defeat an anti-bot page itself: a challenged
shop is recorded as blocked and disabled. Routes past edge walls (public search
APIs, Chrome fingerprint, real Chrome) are pinned in sites_config.MANUAL_OVERRIDES.

Usage:  python -m scripts.probe_stores [--only id1,id2] [--workers 8] [--no-browser]
"""
import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.sites_config import (  # noqa: E402
    DEFAULT_USER_AGENT,
    MANUAL_OVERRIDES,
    OVERRIDES_FILE,
    PLATFORM_SEARCH_URLS,
    load_stores,
)
from scrapers.structured import extract_any  # noqa: E402

REPORT_FILE = Path(__file__).resolve().parents[1] / "data" / "store_probe.json"
QUERY = "fender"
TIMEOUT = 25
HEADERS = {
    "User-Agent": DEFAULT_USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
    "Accept-Language": "en;q=0.9",
}

HTML_CANDIDATES = (
    "/search?q={query}",
    "/search?search={query}",  # Shopware 6
    "/catalogsearch/result/?q={query}",
    "/?s={query}&post_type=product",
    "/search.php?search_query={query}",
    "/search/?q={query}",
)

# SEO-spam doorway pages injected into hacked shops, and localized spam mirrors:
# they parse as perfect product grids, so they have to be rejected explicitly.
SPAM_MARKERS = ("slot online", "situs slot", "judi bola", "togel", "casino online")

ANTIBOT_MARKERS = (
    "just a moment",
    "checking your browser",
    "cf-browser-verification",
    "enable javascript and cookies to continue",
    "captcha",
    "access denied",
    "request unsuccessful",
    "incapsula",
    "datadome",
    "px-captcha",
)

SEARCH_PARAM_NAMES = {
    "q", "s", "query", "search", "keyword", "keywords", "term", "text",
    "ssearch", "searchword", "search_query", "keywordfreeword", "sw", "wd",
}
SEARCH_WORDS = ("search", "suche", "recherche", "cerca", "ricerca", "busca",
                "arama", "検索", "zoek", "sok", "hledat")


def detect_platform(html: str, headers: dict) -> str:
    h = {k.lower(): str(v).lower() for k, v in headers.items()}
    low = html.lower()
    if "x-shopify-stage" in h or "x-sorting-hat-shopid" in h or "cdn.shopify.com" in low \
            or "shopify.theme" in low:
        return "shopify"
    if "woocommerce" in low or "wp-content/plugins/woocommerce" in low:
        return "woocommerce"
    if "x-magento-vary" in h.get("set-cookie", "") or "/static/version" in low \
            or "magento_" in low or "mage/cookies" in low:
        return "magento"
    if "prestashop" in low:
        return "prestashop"
    if "cdn11.bigcommerce.com" in low or "bigcommerce" in low:
        return "bigcommerce"
    if "shopware" in low or "/widgets/" in low and "sw-" in low:
        return "shopware"
    if "wp-content" in low or "wp-json" in low:
        return "wordpress"
    if "static1.squarespace.com" in low:
        return "squarespace"
    if "wixstatic.com" in low:
        return "wix"
    return "custom"


def _antibot(text: str, status: int = 200) -> bool:
    """Anti-bot interstitials are short pages; a shop page may mention 'captcha'
    in its own copy, so only judge small bodies or error responses."""
    low = text[:4000].lower()
    if not any(m in low for m in ANTIBOT_MARKERS):
        return False
    return status != 200 or len(text) < 5000


def search_routes_from_home(html: str, origin: str) -> list[str]:
    """Read the shop's own search form(s) to learn its real search route."""
    soup = BeautifulSoup(html, "lxml")
    routes: list[str] = []
    for form in soup.find_all("form"):
        action = (form.get("action") or "").strip()
        blob = " ".join(
            [action, form.get("id") or "", " ".join(form.get("class") or []),
             form.get("role") or "", form.get("name") or ""]
        ).lower()
        text_inputs = [
            i for i in form.find_all("input")
            if (i.get("type") or "text").lower() in ("text", "search") and i.get("name")
        ]
        if not text_inputs:
            continue
        param = text_inputs[0]["name"]
        looks_like_search = (
            param.lower() in SEARCH_PARAM_NAMES
            or any(w in blob for w in SEARCH_WORDS)
            or any(w in (i.get("placeholder") or "").lower()
                   for i in text_inputs for w in SEARCH_WORDS)
        )
        if not looks_like_search:
            continue
        url = urljoin(origin + "/", action or "/")
        hidden = {
            i["name"]: i.get("value") or ""
            for i in form.find_all("input", attrs={"type": "hidden"})
            if i.get("name") and i.get("value")
        }
        parts = [f"{param}={{query}}"] + [f"{k}={v}" for k, v in list(hidden.items())[:3]]
        route = url + ("&" if "?" in url else "?") + "&".join(parts)
        if route not in routes:
            routes.append(route)
    return routes[:2]


def _host_variants(url: str) -> list[str]:
    """The start URL, then the same host with/without `www.`, then plain http."""
    split = urlsplit(url)
    host = split.netloc
    other = host[4:] if host.startswith("www.") else f"www.{host}"
    variants = [url.rstrip("/"), f"{split.scheme}://{other}"]
    if split.scheme == "https":
        variants.append(f"http://{host}")
    seen, out = set(), []
    for v in variants:
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out


class Probe:
    def __init__(self, store: dict, use_browser: bool = True):
        self.store = store
        self.id = store["id"]
        self.use_browser = use_browser
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.out = {
            "id": self.id,
            "name": store["name"],
            "url": store["url"],
            "area": store["area"],
            "home_status": None,
            "final_url": None,
            "platform": None,
            "search_url": None,
            "scraper_type": None,
            "data_quality": None,
            "products_found": 0,
            "robots_allows_search": True,
            "status": "unknown",
            "blocked_reason": None,
            "attempts": [],
            "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        self._robots: RobotFileParser | None = None

    # ---------- helpers ----------
    def _get(self, url: str) -> requests.Response:
        resp = self.session.get(url, timeout=TIMEOUT, allow_redirects=True)
        # Same charset sniffing as BaseScraper: Japanese shops often omit it.
        if "charset=" not in (resp.headers.get("content-type") or "").lower():
            resp.encoding = resp.apparent_encoding or resp.encoding
        return resp

    def robots_ok(self, url: str) -> bool:
        origin = "{0.scheme}://{0.netloc}".format(urlsplit(url))
        if self._robots is None:
            rp = RobotFileParser()
            try:
                resp = self._get(urljoin(origin, "/robots.txt"))
                rp.parse(resp.text.splitlines() if resp.status_code == 200 else [])
            except Exception:  # noqa: BLE001 — no robots.txt means no rules
                rp.parse([])
            self._robots = rp
        try:
            return self._robots.can_fetch(DEFAULT_USER_AGENT, url)
        except Exception:  # noqa: BLE001
            return True

    def _count_json(self, url: str, platform: str) -> tuple[int, int | None]:
        resp = self._get(url)
        if resp.status_code != 200:
            return 0, resp.status_code
        try:
            data = resp.json()
        except ValueError:
            return 0, resp.status_code
        if platform == "shopify":
            items = data.get("products", []) if isinstance(data, dict) else []
            items = [i for i in items if isinstance(i, dict) and i.get("variants")]
        else:  # WooCommerce Store API — some installs answer with bare ids
            items = data if isinstance(data, list) else []
            items = [i for i in items if isinstance(i, dict) and i.get("prices")]
        return len(items), resp.status_code

    def _count_markup(self, html: str) -> tuple[int, str | None]:
        if any(m in html[:200000].lower() for m in SPAM_MARKERS):
            self.out["attempts"].append({"result": "rejected: spam doorway content"})
            return 0, None
        records, quality = extract_any(html)
        # A route that prices everything in a currency the shop does not use is
        # the wrong storefront (locale mirror, spam clone, marketplace embed).
        found = {r["currency"] for r in records if r.get("currency")}
        expected = self.store["local_currency"]
        if found and expected not in found:
            self.out["attempts"].append(
                {"result": f"rejected: prices in {sorted(found)}, shop uses {expected}"}
            )
            return 0, None
        return len(records), quality

    def _count_html(self, url: str) -> tuple[int, int | None, str | None]:
        resp = self._get(url)
        if resp.status_code != 200 or _antibot(resp.text, resp.status_code):
            return 0, resp.status_code, None
        count, quality = self._count_markup(resp.text)
        return count, resp.status_code, quality

    def _count_rendered(self, url: str) -> tuple[int, str | None]:
        """Last resort: render in Chromium (client-side grids). No captcha work."""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return 0, None
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
                )
                ctx = browser.new_context(locale="en-US", viewport={"width": 1366, "height": 900})
                page = ctx.new_page()
                page.goto(url, timeout=45000, wait_until="domcontentloaded")
                page.wait_for_timeout(3500)
                html = page.content()
                browser.close()
        except Exception as exc:  # noqa: BLE001
            self.out["attempts"].append({"url": url, "result": f"render:{type(exc).__name__}"})
            return 0, None
        if _antibot(html):
            self.out["attempts"].append({"url": url, "result": "render:anti-bot challenge"})
            return 0, None
        return self._count_markup(html)

    # ---------- main ----------
    def run(self) -> dict:
        store = self.store
        if self.id in MANUAL_OVERRIDES:
            man = MANUAL_OVERRIDES[self.id]
            self.out.update(status="manual", platform=man.get("platform"),
                            search_url=man.get("search_url"),
                            scraper_type=man.get("scraper_type"))
            return self.out

        # Shops move between www and apex, and a few only answer on one of them
        # (expired certificate on the other), so try the variants before giving up.
        home, last_error = None, None
        for base in _host_variants(store["url"]):
            try:
                home = self._get(base)
                break
            except Exception as exc:  # noqa: BLE001
                last_error = f"{type(exc).__name__}: {exc}"[:200]
                self.out["attempts"].append({"url": base, "result": type(exc).__name__})
        if home is None:
            self.out.update(status="unreachable", blocked_reason=last_error)
            return self.out

        self.out["home_status"] = home.status_code
        self.out["final_url"] = home.url
        if home.status_code in (401, 403, 429) or _antibot(home.text, home.status_code):
            self.out.update(
                status="blocked",
                blocked_reason=f"anti-bot or forbidden (HTTP {home.status_code})",
                platform=detect_platform(home.text, dict(home.headers)),
            )
            return self.out
        if home.status_code >= 500:
            self.out.update(status="unreachable", blocked_reason=f"HTTP {home.status_code}")
            return self.out

        platform = detect_platform(home.text, dict(home.headers))
        self.out["platform"] = platform
        split = urlsplit(home.url)
        origin = f"{split.scheme}://{split.netloc}"

        # (url_template, scraper_type, kind, probe_url). The probe URL differs
        # for WooCommerce: the Store API is validated with an unfiltered request,
        # because a shop that simply sells no Fender gear would otherwise look
        # broken. At runtime the scraper uses the `search=` template.
        woo_template = PLATFORM_SEARCH_URLS["woocommerce"].format(base=origin)
        candidates: list[tuple[str, str, str, str | None]] = [
            (PLATFORM_SEARCH_URLS["shopify"].format(base=origin), "shopify", "json", None),
            (woo_template, "woocommerce", "json",
             f"{origin}/wp-json/wc/store/v1/products?per_page=5"),
            # WordPress installs without pretty permalinks only answer here.
            (f"{origin}/?rest_route=/wc/store/v1/products&search={{query}}&per_page=24",
             "woocommerce", "json",
             f"{origin}/?rest_route=/wc/store/v1/products&per_page=5"),
        ]
        if platform in ("woocommerce", "wordpress"):
            candidates.reverse()
        form_routes = search_routes_from_home(home.text, origin)
        candidates += [(r, "structured", "html", None) for r in form_routes]
        candidates += [
            (origin + path, "structured", "html", None)
            for path in HTML_CANDIDATES
            if origin + path not in form_routes
        ]

        attempts = self.out["attempts"]
        allowed_any = False
        html_routes_tried: list[str] = []
        for search_url, scraper_type, kind, probe_override in candidates:
            probe_url = probe_override or (
                search_url.format(query=QUERY) if "{query}" in search_url else search_url
            )
            if not self.robots_ok(probe_url):
                attempts.append({"url": probe_url, "result": "robots_disallowed"})
                continue
            allowed_any = True
            try:
                if kind == "json":
                    count, status = self._count_json(probe_url, scraper_type)
                    quality = "structured"
                else:
                    count, status, quality = self._count_html(probe_url)
                    if status == 200:
                        html_routes_tried.append(search_url)
            except Exception as exc:  # noqa: BLE001
                attempts.append({"url": probe_url, "result": type(exc).__name__})
                continue
            attempts.append({"url": probe_url, "http": status, "products": count,
                             "quality": quality if count else None})
            self.out["search_status"] = status
            if count:
                self.out.update(search_url=search_url, scraper_type=scraper_type,
                                products_found=count, data_quality=quality, status="ok")
                return self.out
            time.sleep(1.0)  # polite gap between candidate probes on one domain

        # Client-side rendered grids: retry the routes that answered 200.
        if self.use_browser:
            for search_url in html_routes_tried[:2]:
                count, quality = self._count_rendered(search_url.format(query=QUERY))
                if count:
                    self.out.update(search_url=search_url, scraper_type="playwright",
                                    products_found=count, data_quality=quality,
                                    status="ok_rendered")
                    return self.out

        self.out["robots_allows_search"] = allowed_any
        if not allowed_any:
            self.out.update(status="robots_disallowed",
                            blocked_reason="robots.txt disallows every known search route")
        else:
            self.out.update(
                status="no_search_results",
                blocked_reason="no product data found on any known search route",
            )
        return self.out

    def close(self) -> None:
        self.session.close()


def probe_store(store: dict, use_browser: bool = True) -> dict:
    p = Probe(store, use_browser=use_browser)
    try:
        return p.run()
    finally:
        p.close()


def write_results(results: dict[str, dict]) -> dict[str, int]:
    report = {}
    if REPORT_FILE.exists():
        report = json.loads(REPORT_FILE.read_text(encoding="utf-8"))
    report.update(results)
    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    overrides = {}
    if OVERRIDES_FILE.exists():
        overrides = json.loads(OVERRIDES_FILE.read_text(encoding="utf-8"))
    for sid, res in results.items():
        if sid in MANUAL_OVERRIDES:
            continue  # hand-written scrapers own their config
        ov = {
            "platform": res.get("platform") or "unknown",
            "robots_allows_search": res.get("robots_allows_search", True),
            "probe_status": res.get("status"),
            "probe_products": res.get("products_found", 0),
            "probed_at": res.get("checked_at"),
        }
        if res.get("search_url"):
            ov["search_url"] = res["search_url"]
            ov["scraper_type"] = res["scraper_type"]
            ov["data_quality"] = res.get("data_quality")
            # JSON feeds, schema.org markup and the shop's own embedded JSON are
            # canonical; grid detection is best-effort and flagged as such.
            ov["selectors_verified"] = res.get("data_quality") in ("structured", "inline_json")
            ov["requires_javascript"] = res["scraper_type"] == "playwright"
        if res.get("status") not in ("ok", "ok_rendered"):
            ov["enabled"] = False
            ov["blocked_reason"] = res.get("blocked_reason")
        overrides[sid] = ov
    OVERRIDES_FILE.write_text(
        json.dumps(overrides, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8"
    )

    counts: dict[str, int] = {}
    for res in report.values():
        counts[res.get("status", "unknown")] = counts.get(res.get("status", "unknown"), 0) + 1
    return counts


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="comma-separated store ids")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--no-browser", action="store_true", help="skip the Chromium fallback")
    args = ap.parse_args()

    stores = load_stores()
    if args.only:
        wanted = {s.strip() for s in args.only.split(",")}
        stores = [s for s in stores if s["id"] in wanted]

    results: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(probe_store, s, not args.no_browser): s["id"] for s in stores}
        for i, fut in enumerate(as_completed(futures), 1):
            sid = futures[fut]
            try:
                res = fut.result()
            except Exception as exc:  # noqa: BLE001
                res = {"id": sid, "status": "probe_error", "blocked_reason": str(exc)[:200]}
            results[sid] = res
            print(
                f"[{i:3}/{len(stores)}] {sid:45} {str(res.get('status')):18} "
                f"{str(res.get('platform')):12} n={res.get('products_found', 0):3} "
                f"{res.get('data_quality') or ''}",
                flush=True,
            )

    counts = write_results(results)
    print("\nsummary:", json.dumps(counts, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
