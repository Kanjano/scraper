"""Suggested-price computation from multi-site offers (all in EUR)."""
from statistics import mean, median

from config.settings import settings


class PricingEngine:
    def __init__(self):
        self.base_discount = 1.0 - settings.price_discount_multiplier  # e.g. 0.07
        self.max_discount = settings.margin_max_percent / 100.0

    def calculate_suggested_price(self, offers: list[dict]) -> dict:
        """offers: [{site, price_eur, reviews, stock}, ...] (price_eur required)."""
        priced = [o for o in offers if o.get("price_eur")]
        if not priced:
            return {"error": "no priced offers"}

        prices = [o["price_eur"] for o in priced]
        lowest = min(priced, key=lambda o: o["price_eur"])
        market_avg = round(mean(prices), 2)
        med = median(prices)

        # Filter outliers (>2x median) for a robust low anchor.
        sane = [p for p in prices if p <= 2 * med] or prices
        anchor = min(sane)

        best = max(priced, key=lambda o: o.get("reviews", 0))
        discount = self.base_discount
        reasons = [f"base discount {self.base_discount:.0%}"]
        if best.get("reviews", 0) > 500:
            discount += 0.03
            reasons.append("+3% bestseller (>500 reviews)")
        if (best.get("stock") or 0) > 20:
            discount += 0.02
            reasons.append("+2% high stock (>20)")
        discount = min(discount, self.max_discount)
        reasons.append(f"discount capped at {self.max_discount:.0%}")

        suggested = round(anchor * (1 - discount), 2)
        margin_amount = round(anchor - suggested, 2)
        margin_pct = round(discount * 100, 2)

        return {
            "price_suggested": suggested,
            "margin_percentage": margin_pct,
            "margin_amount": margin_amount,
            "lowest_price_site": lowest["site"],
            "lowest_price": lowest["price_eur"],
            "market_average": market_avg,
            "total_sites_analyzed": len(priced),
            "reasoning": "; ".join(reasons)
            + f"; anchor={anchor} EUR (lowest non-outlier of {len(priced)} offers)",
        }
