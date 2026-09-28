"""Playwright-rendered scraper base for JS-heavy sites.

Renders the search page in a real Chromium with light stealth tweaks, then
reuses the CSS-selector parsing from GenericScraper. Use for sites whose product
grid/prices are injected by JavaScript.

With ``stealth: true`` in the store config the page is rendered by patchright (a
Playwright fork without the CDP automation leaks) driving the installed Google
Chrome, with the "Headless" token removed from the user-agent. That clears
Cloudflare's non-interactive JS challenge and PerimeterX; it is not a captcha
solver — interactive challenges (Turnstile checkbox, Akamai press-and-hold)
still need a proxy/unlocker.

Requires: pip install playwright && playwright install chromium
          stealth: pip install patchright + Google Chrome installed
"""
from urllib.parse import quote_plus, urljoin

from bs4 import BeautifulSoup

from config.settings import settings
from scrapers.parsers import first_attr, img_src, link_node, name_text, text_or_none
from scrapers.sites.generic_scraper import GenericScraper
from scrapers.structured import extract_any
from utils.proxy_manager import ProxyManager

# Removes the most common automation fingerprint before page scripts run.
_STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'languages', {get: () => ['en-US','en']});
Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
window.chrome = { runtime: {} };
"""


class PlaywrightScraper(GenericScraper):
    def _render_html(self, url: str) -> str | None:
        stealth = bool(self.config.get("stealth"))
        if stealth:
            from patchright.sync_api import sync_playwright
        else:
            from playwright.sync_api import sync_playwright

        wait_for = self.config["selectors"].get("product_container")
        ua = self.config.get("headers", {}).get("User-Agent")
        proxy = ProxyManager.as_playwright(self.proxy_manager.next_proxy())
        if proxy:
            self.logger.info("using proxy %s", proxy["server"])
        self.rate_limiter.wait()
        try:
            with sync_playwright() as p:
                if stealth:
                    browser = p.chromium.launch(
                        channel="chrome", headless=settings.headless_browser, proxy=proxy
                    )
                    # The real UA of this Chrome build, minus the "HeadlessChrome"
                    # token that every bot wall checks first.
                    probe = browser.new_page()
                    ua = probe.evaluate("navigator.userAgent").replace("HeadlessChrome", "Chrome")
                    probe.close()
                else:
                    browser = p.chromium.launch(
                        headless=settings.headless_browser,
                        proxy=proxy,
                        args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
                    )
                ctx = browser.new_context(
                    user_agent=ua,
                    viewport={"width": 1366, "height": 900},
                    locale="en-US",
                )
                if not stealth:  # patchright patches these natively; the shim would leak
                    ctx.add_init_script(_STEALTH_JS)
                page = ctx.new_page()
                page.goto(url, timeout=self.timeout * 1000, wait_until="domcontentloaded")
                page.wait_for_timeout(2500)  # let client-side grids render
                if wait_for:
                    try:
                        page.wait_for_selector(wait_for, timeout=self.timeout * 1000)
                    except Exception:  # noqa: BLE001
                        self.logger.warning("product selector never appeared on %s", url)
                html = page.content()
                browser.close()
                return html
        except Exception as exc:  # noqa: BLE001
            self.logger.error("playwright render failed: %s", exc)
            return None

    def search(self, query: str, limit: int = 20, **kwargs) -> list[dict]:
        sel = self.config.get("selectors") or {}
        url = self.config["search_url"].format(query=quote_plus(query))
        html = self._render_html(url)
        if not html:
            return []

        if sel.get("product_container"):
            records = self._from_selectors(html, sel, limit)
            if records:
                return self.finalize(records)
            self.logger.warning("selectors matched nothing, falling back to markup parsing")

        # No usable selectors: schema.org → embedded JSON → grid detection.
        records, _quality = extract_any(html, limit=limit)
        out = []
        for rec in records[:limit]:
            rec["currency"] = rec.get("currency") or self.currency
            for key in ("url", "image"):
                if rec.get(key):
                    rec[key] = urljoin(self.config["url"], rec[key])
            out.append(rec)
        return self.finalize(out)

    def _from_selectors(self, html: str, sel: dict, limit: int) -> list[dict]:
        soup = BeautifulSoup(html, "lxml")

        records: list[dict] = []
        for node in soup.select(sel["product_container"])[:limit]:
            href = first_attr(link_node(node, sel.get("url")), "href")
            brand = (
                text_or_none(node.select_one(sel["brand"])) if sel.get("brand") else None
            )
            was = self.parse_price(text_or_none(node.select_one(sel["original_price"])) or "") \
                if sel.get("original_price") else None
            image = img_src(node.select_one(sel.get("image", "img")))
            records.append(
                {
                    "name": name_text(node.select_one(sel["name"])),
                    "brand": brand,
                    "price": self.parse_price(
                        text_or_none(node.select_one(sel["price"])) or ""
                    ),
                    "currency": self.currency,
                    "rating": None,
                    "url": urljoin(self.config["url"], href) if href else None,
                    "external_id": href,
                    "original_price": was,
                    "image": urljoin(self.config["url"], image) if image else None,
                }
            )
        return [r for r in records if r.get("name") and r.get("price")]
