"""Aggregate market statistics over scraped instruments."""
from statistics import mean
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models import Instrument, PriceHistory


class MarketAnalyzer:
    def __init__(self, db: Session):
        self.db = db

    def market_overview(self) -> dict:
        rows = self.db.execute(
            select(Instrument.category, func.count(), func.avg(Instrument.price_eur_equivalent))
            .where(Instrument.price_eur_equivalent.is_not(None))
            .group_by(Instrument.category)
        ).all()
        categories = [
            {"category": c or "uncategorized", "count": n, "avg_price_eur": round(a or 0, 2)}
            for c, n, a in rows
        ]
        total = sum(c["count"] for c in categories)
        overall = round(mean([c["avg_price_eur"] for c in categories]), 2) if categories else 0
        return {
            "total_instruments": total,
            "overall_avg_price_eur": overall,
            "categories": sorted(categories, key=lambda c: -c["count"]),
        }

    def price_trend(self, instrument_id: int, days: int = 30) -> dict:
        since = datetime.utcnow() - timedelta(days=days)
        rows = self.db.execute(
            select(PriceHistory.date, PriceHistory.price_normalized)
            .where(PriceHistory.instrument_id == instrument_id, PriceHistory.date >= since)
            .order_by(PriceHistory.date)
        ).all()
        points = [{"date": d.isoformat(), "price_eur": p} for d, p in rows if p]
        trend = "flat"
        if len(points) >= 2:
            delta = points[-1]["price_eur"] - points[0]["price_eur"]
            trend = "up" if delta > 0 else "down" if delta < 0 else "flat"
        return {"instrument_id": instrument_id, "days": days, "trend": trend, "points": points}
