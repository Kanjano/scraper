"""Schema.org extraction: one parser for any shop that publishes product data.

Most e-commerce platforms (Magento, PrestaShop, BigCommerce, Squarespace, and
plenty of custom builds) emit JSON-LD ``Product``/``ItemList`` blocks or
microdata on their listing pages — put there for Google Shopping, so they stay
accurate. Reading that beats guessing CSS classes per shop: no per-site
selectors to maintain, and it breaks loudly rather than silently.
"""
import json

from bs4 import BeautifulSoup

from scrapers.parsers import img_src, parse_price

_PRODUCT_TYPES = {"product", "productgroup", "individualproduct", "vehicle"}


def _as_list(val):
    if val is None:
        return []
    return val if isinstance(val, list) else [val]


def _is_product(node: dict) -> bool:
    types = {str(t).lower() for t in _as_list(node.get("@type"))}
    return bool(types & _PRODUCT_TYPES)


def _walk(node, out: list[dict]) -> None:
    """Collect every Product-ish dict anywhere in a JSON-LD graph."""
    if isinstance(node, list):
        for item in node:
            _walk(item, out)
        return
    if not isinstance(node, dict):
        return
    if _is_product(node):
        out.append(node)
    for key in ("@graph", "itemListElement", "item", "mainEntity", "hasPart"):
        if key in node:
            _walk(node[key], out)


def _offer_fields(node: dict) -> tuple[float | None, str | None, int | None]:
    """First concrete price found in offers/aggregateOffer."""
    for offer in _as_list(node.get("offers")):
        if not isinstance(offer, dict):
            continue
        for price_key in ("price", "lowPrice", "highPrice"):
            price = parse_price(str(offer.get(price_key))) if offer.get(price_key) else None
            if price:
                avail = str(offer.get("availability", "")).lower()
                stock = None
                if avail:
                    stock = 0 if "outofstock" in avail or "soldout" in avail else 1
                return price, offer.get("priceCurrency"), stock
        nested = _offer_fields(offer)  # AggregateOffer wrapping Offers
        if nested[0]:
            return nested
    return None, None, None


def _list_price(node: dict) -> float | None:
    """Pre-discount price: a StrikethroughPrice / ListPrice price specification."""
    for offer in _as_list(node.get("offers")):
        if not isinstance(offer, dict):
            continue
        for spec in _as_list(offer.get("priceSpecification")):
            if isinstance(spec, dict) and any(
                k in str(spec.get("priceType", "")) for k in ("Strikethrough", "ListPrice", "MSRP")
            ):
                return parse_price(str(spec.get("price"))) if spec.get("price") else None
        nested = _list_price(offer)
        if nested:
            return nested
    return None


def _image(node: dict) -> str | None:
    img = node.get("image")
    if isinstance(img, list):
        img = img[0] if img else None
    if isinstance(img, dict):
        img = img.get("url") or img.get("contentUrl")
    return img if isinstance(img, str) else None


def products_from_jsonld(soup: BeautifulSoup) -> list[dict]:
    found: list[dict] = []
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = tag.string or tag.get_text() or ""
        try:
            data = json.loads(raw.strip())
        except (json.JSONDecodeError, ValueError):
            continue
        _walk(data, found)

    records: list[dict] = []
    for node in found:
        price, currency, stock = _offer_fields(node)
        brand = node.get("brand")
        if isinstance(brand, dict):
            brand = brand.get("name")
        rating = (node.get("aggregateRating") or {}).get("ratingValue") \
            if isinstance(node.get("aggregateRating"), dict) else None
        reviews = (node.get("aggregateRating") or {}).get("reviewCount") \
            if isinstance(node.get("aggregateRating"), dict) else None
        records.append(
            {
                "name": node.get("name"),
                "brand": brand if isinstance(brand, str) else None,
                "price": price,
                "currency": currency,
                "url": node.get("url") if isinstance(node.get("url"), str) else None,
                "external_id": str(node.get("sku") or node.get("productID") or "") or None,
                "rating": parse_price(str(rating)) if rating else None,
                "reviews": int(reviews) if str(reviews or "").isdigit() else 0,
                "stock": stock,
                "original_price": _list_price(node),
                "image": _image(node),
            }
        )
    return records


def products_from_microdata(soup: BeautifulSoup) -> list[dict]:
    records: list[dict] = []
    for node in soup.select('[itemtype*="schema.org/Product" i]'):
        name_el = node.select_one('[itemprop="name"]')
        price_el = node.select_one('[itemprop="price"], [itemprop="lowPrice"]')
        link_el = node.select_one('[itemprop="url"], a[href]')
        if not (name_el and price_el):
            continue
        price_raw = price_el.get("content") or price_el.get_text(strip=True)
        cur_el = node.select_one('[itemprop="priceCurrency"]')
        img_el = node.select_one('[itemprop="image"]')
        image = (img_el.get("content") or img_el.get("href") or img_src(img_el)) if img_el else None
        records.append(
            {
                "name": name_el.get("content") or name_el.get_text(strip=True),
                "brand": None,
                "price": parse_price(str(price_raw)),
                "currency": (cur_el.get("content") if cur_el else None),
                "url": (link_el.get("content") or link_el.get("href")) if link_el else None,
                "external_id": None,
                "rating": None,
                "stock": None,
                "image": image or img_src(node.find("img")),
            }
        )
    return records


def extract_any(html: str, limit: int = 60) -> tuple[list[dict], str | None]:
    """Best available reading of a listing page, and how it was obtained.

    schema.org markup → JSON embedded for the page's own JS → repeated-grid
    detection. The label says how much to trust the numbers: the first two are
    the shop's own data, the last one is inferred from layout.
    """
    from scrapers.grid import heuristic_products
    from scrapers.inline_json import products_from_inline_json

    for records, quality in (
        (extract_products(html), "structured"),
        (products_from_inline_json(html, limit=limit), "inline_json"),
        (heuristic_products(html, limit=limit), "heuristic"),
    ):
        priced = [r for r in records if r.get("price")]
        if priced:
            return priced[:limit], quality
    return [], None


def extract_products(html: str) -> list[dict]:
    """JSON-LD first, microdata as backup. Deduped by (name, price)."""
    soup = BeautifulSoup(html, "lxml")
    records = products_from_jsonld(soup) or products_from_microdata(soup)
    seen, out = set(), []
    for rec in records:
        key = (rec.get("name"), rec.get("price"))
        if not rec.get("name") or key in seen:
            continue
        seen.add(key)
        out.append(rec)
    return out
