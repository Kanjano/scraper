"""Validation / normalization of raw scraped records."""
from utils.currency_converter import converter

REQUIRED = ("name", "price")


def is_valid(record: dict) -> bool:
    if not record.get("name"):
        return False
    price = record.get("price")
    return isinstance(price, (int, float)) and price > 0


def normalize(record: dict, currency: str) -> dict:
    record.setdefault("currency", currency)
    record.setdefault("reviews", 0)
    record.setdefault("brand", None)
    record["price_eur_equivalent"] = converter.to_base(
        float(record["price"]), record["currency"]
    )
    # A discount counts only when the pre-sale price is plausibly the same
    # product's (1-90% off): a bigger gap means the shop's markup was misread.
    was = record.get("original_price")
    price = float(record["price"])
    if isinstance(was, (int, float)) and price * 1.01 < was <= price * 10:
        record["discount_pct"] = round((1 - price / was) * 100)
        record["original_price_eur"] = converter.to_base(float(was), record["currency"])
    else:
        record["original_price"] = None
        record["discount_pct"] = 0
    return record
