"""Price history and computed suggested-price models."""
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from config.database import Base


class PriceHistory(Base):
    __tablename__ = "price_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id"), index=True)
    price: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(3))
    site_name: Mapped[str] = mapped_column(String(100))
    price_normalized: Mapped[float | None] = mapped_column(Float, nullable=True)
    date: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)


class SuggestedPrice(Base):
    __tablename__ = "suggested_prices"

    id: Mapped[int] = mapped_column(primary_key=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id"), index=True)
    price_suggested: Mapped[float] = mapped_column(Float)
    margin_percentage: Mapped[float] = mapped_column(Float)
    margin_amount: Mapped[float] = mapped_column(Float)
    lowest_price_site: Mapped[str | None] = mapped_column(String(100), nullable=True)
    lowest_price_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    market_avg_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_sites_analyzed: Mapped[int] = mapped_column(Integer, default=0)
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    valid_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
