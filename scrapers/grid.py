"""Selector-free product-grid extraction.

Shops that publish no schema.org data still render their listing as a repeated
block holding a link, a title and a price. This finds that repetition instead of
hard-coding CSS classes per shop:

1. collect every element that contains a price text *and* a link and is small
   enough to be a card (not a whole page section);
2. drop the ones that contain another such element, keeping the innermost cards;
3. keep the largest group of cards sharing a parent — that group is the grid.

One parser for every HTML storefront; it returns nothing rather than garbage
when a page has no repeating priced blocks.
"""
import re

from bs4 import BeautifulSoup

from scrapers.parsers import img_src, parse_price

# Currency symbols/codes across the dataset (EU, US, UK, CH, JP, CZ, TR, AE,
# SG, HK, IN, KR).
# Includes the full-width yen sign (￥, U+FFE5) used on Japanese shops and the
# won sign, which are distinct code points from ¥ / W.
_CUR = (r"(?:[$€£¥₹]|￥|₩|₺|Kč|CHF|Fr\.|USD|EUR|GBP|JPY|CZK|TRY|AED|SGD|HKD|INR|"
        r"KRW|TL|S\$|HK\$|Rs\.?|円|元|税込)")
_NUM = r"\d{1,3}(?:[.,\s]\d{3})*(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,2})?"
_PRICE_RE = re.compile(rf"(?:{_CUR}\s*(?:{_NUM}))|(?:(?:{_NUM})\s*{_CUR})")

# Numbers that are not the product's price.
_SKIP_TEXT = re.compile(
    r"(free shipping|free next day|spedizione|versand|livraison|financing|"
    r"per month|/mo\b|a month|as low as|starting at|a partire da|ab nur|"
    r"gift ?card|subtotal|total:|vat|iva inclusa|rules apply|voir cgv|"
    r"save |you save|risparmi|coupon|rrp|msrp|was |"
    # Japanese instalment/interest banners: "最長48回払い金利0％", "分割金利"
    r"回払い|金利|分割払い|送料無料)",
    re.I,
)
# Card titles that are navigation or marketing copy.
_BAD_NAME = re.compile(
    r"^(view|shop|help|menu|cart|sign ?in|log ?in|faq|most common|advice|rules|"
    r"free|see |click|read more|filter|sort|search|home|next|previous|select |"
    r"newsletter|contact|about|all |more info|learn more|checkout|add to|"
    r"\d+ (results?|items?|products?))",
    re.I,
)
_BAD_HREF = re.compile(r"^(#|javascript:|mailto:|tel:)")
_PRICEY = re.compile(r"price|amount|cost|prezzo|preis|prix|precio", re.I)
# The price before the discount: struck through, or tagged as old/list price.
_STRUCK_TAGS = {"s", "del", "strike"}
_STRUCK = re.compile(
    r"\bold|was-?price|strike|compare|before|list-?price|crossed|uvp|rrp|"
    r"prezzo-?barrato|streich|ancien|precio-?anterior|original-?price", re.I,
)
# Instalment / financing blocks: their prices are monthly payments, not the price.
_FINANCE = re.compile(
    r"financ|instal|klarna|affirm|afterpay|paypal|credit|monthly|per-?month|"
    r"\brata|\brate\b|ratenzahl|monat|mensual|taksit|\bemi\b|ala-price|payment",
    re.I,
)
# Text right after a price that makes it a per-period amount: "$392 /month".
_PER_PERIOD = re.compile(
    r"^\s*(?:/|per\b|a\b|al\b|pro\b|par\b|im\b|x\s*\d+)?\s*"
    r"(?:mo\b|mth|month|mese|mesi|mes\b|meses|monat|mois|ay\b|aylık|月|ヶ月|か月|개월|回)",
    re.I,
)

_MIN_CARDS = 3
_MAX_CARD_TEXT = 600
_MAX_CARD_PRICES = 6


def _attrs(tag) -> str:
    return " ".join(
        [" ".join(tag.get("class", []) or []), tag.get("id", "") or ""]
        + [str(v) for k, v in (tag.attrs or {}).items() if k.startswith("data-")]
    )


def _is_instalment(tag) -> bool:
    """Inside a financing block, or followed by "/month" and the like."""
    probe = tag
    for _ in range(4):
        if probe is None or probe.name in ("li", "article", "tr"):
            break
        if _FINANCE.search(_attrs(probe)):
            return True
        probe = probe.parent
    after = []
    for sib in tag.next_siblings:
        after.append(sib.get_text(" ") if hasattr(sib, "get_text") else str(sib))
        if len("".join(after)) > 20:
            break
    return bool(_PER_PERIOD.match("".join(after)))


def _prices_in(el) -> list[tuple[float, bool, bool]]:
    """(price, from a price-ish element, struck-through) for each price in `el`."""
    out = []
    for node in el.find_all(string=_PRICE_RE):
        parent = node.parent
        if parent is None:
            continue
        text = parent.get_text(" ", strip=True)
        if _SKIP_TEXT.search(text) or _is_instalment(parent):
            continue
        m = _PRICE_RE.search(text)
        price = parse_price(m.group(0)) if m else None
        if price is None or price < 1 or price > 5_000_000:
            continue
        pricey = struck = False
        probe = parent
        for _ in range(3):
            if probe is None:
                break
            attrs = _attrs(probe)
            struck = struck or probe.name in _STRUCK_TAGS or bool(_STRUCK.search(attrs))
            pricey = pricey or bool(_PRICEY.search(attrs))
            probe = probe.parent
        out.append((price, pricey, struck))
    # Prices split across elements ("$" "4,699" ".99"): read the joined text of
    # small price-tagged elements.
    for tag in el.find_all(attrs={"class": _PRICEY}):
        joined = tag.get_text("", strip=True)
        if len(joined) > 20 or _SKIP_TEXT.search(joined) or _is_instalment(tag):
            continue
        m = _PRICE_RE.fullmatch(joined)
        price = parse_price(joined) if m else None
        if price and 1 <= price <= 5_000_000 and not any(p == price for p, *_ in out):
            struck = tag.name in _STRUCK_TAGS or bool(_STRUCK.search(_attrs(tag)))
            out.append((price, True, struck))
    return out


def _pick_price(prices: list[tuple[float, bool, bool]]) -> tuple[float | None, float | None]:
    """(current price, price before the discount or None)."""
    if not prices:
        return None, None
    live = [(p, flag) for p, flag, struck in prices if not struck] or [(p, f) for p, f, _ in prices]
    pricey = [p for p, flag in live if flag]
    # Sale price rather than the struck-through one; with no price-tagged element
    # the largest number is the safest guess (small ones are instalments, shipping).
    price = min(pricey) if pricey else max(p for p, _ in live)
    was = [p for p, _, struck in prices if struck and p > price]
    return price, (max(was) if was else None)


def _links(el) -> list:
    return [a for a in el.find_all("a", href=True) if not _BAD_HREF.match(a["href"].strip())]


def _plausible_name(txt: str | None) -> bool:
    if not txt:
        return False
    txt = txt.strip()
    if len(txt) < 6 or len(txt) > 250 or _BAD_NAME.match(txt):
        return False
    return " " in txt or len(txt) >= 12


def _name_from(card) -> str | None:
    for sel in (
        "h1", "h2", "h3", "h4", "h5",
        "[class*=title i]", "[class*=name i]", "strong", "b",
    ):
        for el in card.select(sel):
            txt = el.get_text(" ", strip=True)
            if _plausible_name(txt):
                return txt
    for img in card.find_all("img", alt=True):
        if _plausible_name(img["alt"]):
            return img["alt"].strip()
    best = ""
    for a in _links(card):
        txt = (a.get("title") or a.get("aria-label") or a.get_text(" ", strip=True) or "").strip()
        if _plausible_name(txt) and len(txt) > len(best):
            best = txt
    return best or None


def _candidate_cards(soup) -> list:
    cards = []
    for el in soup.find_all(["li", "div", "article", "section", "td", "tr", "a"]):
        text = el.get_text(" ", strip=True)
        if not text or len(text) > _MAX_CARD_TEXT or not _PRICE_RE.search(text):
            continue
        if not _links(el):
            continue
        prices = _prices_in(el)
        if not prices or len(prices) > _MAX_CARD_PRICES:
            continue
        cards.append(el)
    # Keep innermost cards only.
    return [c for c in cards if not any(other is not c and other in c.descendants for other in cards)]


def heuristic_products(html: str, limit: int = 60) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript", "template"]):
        tag.decompose()
    for tag in soup.select(".sr-only, .visually-hidden, .screen-reader-text"):
        tag.decompose()

    cards = _candidate_cards(soup)
    if not cards:
        return []

    groups: dict[int, list] = {}
    for card in cards:
        groups.setdefault(id(card.parent), []).append(card)
    best = max(groups.values(), key=len)
    chosen = best if len(best) >= _MIN_CARDS else cards

    records, seen = [], set()
    for card in chosen:
        name = _name_from(card)
        price, was = _pick_price(_prices_in(card))
        if not name or not price:
            continue
        key = (name.lower(), price)
        if key in seen:
            continue
        seen.add(key)
        link = _links(card)
        records.append(
            {
                "name": name,
                "brand": None,
                "price": price,
                "currency": None,
                "url": link[0]["href"].strip() if link else None,
                "external_id": None,
                "rating": None,
                "stock": None,
                "original_price": was,
                "image": img_src(card.find("img")),
            }
        )
        if len(records) >= limit:
            break
    return records
