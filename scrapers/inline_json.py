"""Products from JSON embedded in the page.

Single-page storefronts (Wix, Next.js, Nuxt) ship their catalogue as JSON inside
the HTML and build the grid in the browser, so neither schema.org markup nor a
rendered DOM grid is available — but the data is right there. This walks the
page's JSON blobs and keeps every object that carries both a product-ish name and
a price, which is what those payloads look like regardless of framework.
"""
import html
import json
import re

from bs4 import BeautifulSoup

from scrapers.parsers import parse_price

_NAME_KEYS = ("name", "title", "productname", "product_name", "displayname")
_PRICE_KEYS = (
    "price", "formattedprice", "pricevalue", "currentprice", "saleprice",
    "discountedprice", "amount", "lowprice", "minprice",
)
_URL_KEYS = (
    "url", "permalink", "link", "productpageurl", "producturl", "pdpurl",
    "deeplink", "canonicalurl", "href", "handle", "slug",
)
_BRAND_KEYS = ("brand", "vendor", "manufacturer", "make")
_WAS_KEYS = (
    "compareatprice", "compare_at_price", "originalprice", "original_price",
    "regularprice", "regular_price", "listprice", "oldprice", "wasprice",
    "strikethroughprice", "msrp",
)
_IMAGE_KEYS = ("image", "imageurl", "image_url", "img", "thumbnail", "picture",
               "featuredimage", "featured_image", "mainimage")
# `window.__NEXT_DATA__ = {...}` / `window.warmupData = {...}` style assignments.
_ASSIGNMENT_RE = re.compile(
    r"(?:window|self)\.(?:__NEXT_DATA__|__NUXT__|warmupData|__INITIAL_STATE__|"
    r"__APOLLO_STATE__|dataLayer)\s*=\s*(\{)",
)
_MAX_BLOB = 4_000_000


def _first(node: dict, keys: tuple[str, ...]):
    for key, value in node.items():
        if key.lower() in keys and value not in (None, "", [], {}):
            return value
    return None


def _price_of(node: dict, keys: tuple[str, ...] = _PRICE_KEYS) -> float | None:
    raw = _first(node, keys)
    if isinstance(raw, dict):  # {"amount": 1299, "currency": "EUR"}
        raw = _first(raw, _PRICE_KEYS)
    if isinstance(raw, (int, float)):
        price = float(raw)
    elif isinstance(raw, str):
        price = parse_price(raw)
    else:
        return None
    if price is None or price < 1 or price > 5_000_000:
        return None
    return round(price, 2)


def _image_of(node: dict) -> str | None:
    img = _first(node, _IMAGE_KEYS)
    if isinstance(img, list):
        img = img[0] if img else None
    if isinstance(img, dict):
        img = _first(img, ("url", "src", "href"))
    return img if isinstance(img, str) and img.startswith(("http", "/")) else None


def _currency_of(node: dict) -> str | None:
    for key, value in node.items():
        if key.lower() in ("currency", "currencycode", "pricecurrency") and isinstance(value, str):
            return value[:3].upper()
    return None


def _walk(node, out: list[dict], depth: int = 0) -> None:
    if depth > 12:
        return
    if isinstance(node, list):
        for item in node:
            _walk(item, out, depth + 1)
        return
    if not isinstance(node, dict):
        return
    name = _first(node, _NAME_KEYS)
    price = _price_of(node)
    if isinstance(name, str) and 6 <= len(name) <= 250 and price:
        brand = _first(node, _BRAND_KEYS)
        url = _first(node, _URL_KEYS)
        out.append(
            {
                # Embedded payloads often carry HTML-escaped titles ('2&quot;').
                "name": html.unescape(name).strip(),
                "brand": brand if isinstance(brand, str) else None,
                "price": price,
                "currency": _currency_of(node),
                "url": url if isinstance(url, str) else None,
                "external_id": str(node.get("id") or node.get("sku") or "") or None,
                "rating": None,
                "stock": None,
                "original_price": _price_of(node, _WAS_KEYS),
                "image": _image_of(node),
            }
        )
    for value in node.values():
        _walk(value, out, depth + 1)


def _json_blobs(html: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    blobs = [
        tag.string or tag.get_text()
        for tag in soup.find_all("script")
        if (tag.get("type") or "").lower() in ("application/json", "application/ld+json")
        or (tag.get("id") or "").startswith("__")
    ]
    # Framework state assignments: take the balanced object after the `=`.
    for match in _ASSIGNMENT_RE.finditer(html):
        start = match.start(1)
        depth = 0
        for i, ch in enumerate(html[start:start + _MAX_BLOB]):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    blobs.append(html[start:start + i + 1])
                    break
    return [b for b in blobs if b and b.strip().startswith(("{", "["))]


def products_from_inline_json(html: str, limit: int = 60) -> list[dict]:
    found: list[dict] = []
    for blob in _json_blobs(html):
        try:
            data = json.loads(blob)
        except (json.JSONDecodeError, ValueError, RecursionError):
            continue
        _walk(data, found)

    records, seen = [], set()
    for rec in found:
        key = (rec["name"].lower(), rec["price"])
        if key in seen:
            continue
        seen.add(key)
        records.append(rec)
        if len(records) >= limit:
            break
    return records
