"""Generic HTML / price parsing helpers."""
import re

_PRICE_RE = re.compile(r"[-+]?\d[\d.,]*")
# A space between a digit and a following group of three digits is a thousands
# separator ("$3 199.00", "1 299,00 €", common in fr/ch/nordic formatting and on
# shops that render prices with narrow no-break spaces).
_SPACE_GROUP_RE = re.compile(r"(?<=\d)[\s\u00a0\u202f\u2009](?=\d{3}(?:\D|$))")


def parse_price(price_str: str) -> float | None:
    """Convert a localized price string to float.

    Handles both '1.299,99' (EU) and '1,299.99' (US/UK) groupings.
    Returns None when no number is found.
    """
    if price_str is None:
        return None
    if isinstance(price_str, (int, float)):
        return float(price_str)
    cleaned = _SPACE_GROUP_RE.sub("", price_str.replace("\xa0", " "))
    m = _PRICE_RE.search(cleaned)
    if not m:
        return None
    raw = m.group(0)
    if "," in raw and "." in raw:
        # Whichever separator is last is the decimal separator.
        if raw.rfind(",") > raw.rfind("."):
            raw = raw.replace(".", "").replace(",", ".")
        else:
            raw = raw.replace(",", "")
    elif "," in raw:
        # Comma decimal if exactly 2 digits follow it, else thousands sep.
        if re.search(r",\d{2}$", raw):
            raw = raw.replace(".", "").replace(",", ".")
        else:
            raw = raw.replace(",", "")
    elif re.search(r"\.\d{3}$", raw):
        # A lone dot before exactly three digits is a thousands separator in
        # de/it/tr/es formatting ("4.270" = 4270, never 4.27).
        raw = raw.replace(".", "")
    try:
        return round(float(raw), 2)
    except ValueError:
        return None


def text_or_none(node) -> str | None:
    if node is None:
        return None
    txt = node.get_text(strip=True)
    return txt or None


def name_text(node) -> str | None:
    """Text for a product name: parts joined with spaces, so markup like
    "<strong>Fender</strong> Custom Shop" reads "Fender Custom Shop"."""
    if node is None:
        return None
    txt = " ".join(node.get_text(" ", strip=True).split())
    return txt or None


def link_node(card, selector: str | None):
    """The card's link element; ":scope" means the card itself is the <a>."""
    return card if selector == ":scope" else card.select_one(selector or "a")


def first_attr(node, *attrs) -> str | None:
    if node is None:
        return None
    for a in attrs:
        val = node.get(a)
        if val:
            return val
    return None


def img_src(node) -> str | None:
    """Best image URL of an <img>/<source> (lazy-loading attributes first)."""
    if node is None:
        return None
    for attr in ("data-src", "data-lazy-src", "data-original", "src", "data-srcset", "srcset"):
        val = (node.get(attr) or "").strip()
        if not val or val.startswith("data:"):
            continue
        return val.split(",")[0].split()[0]
    return None
