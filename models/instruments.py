"""ORM models for sites and scraped instruments."""
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Boolean,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from config.database import Base


class Site(Base):
    __tablename__ = "sites"

    id: Mapped[int] = mapped_column(primary_key=True)
    # `site_key` is the dataset id from config/stores.json — the stable key used
    # in logs, file names and joins; `name` is only the display label.
    site_key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    url: Mapped[str] = mapped_column(String(255))
    country: Mapped[str] = mapped_column(String(2))
    area: Mapped[str] = mapped_column(String(10), index=True)
    group_name: Mapped[str | None] = mapped_column(String(60), nullable=True)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    specialty: Mapped[str] = mapped_column(String(40), index=True)
    store_type: Mapped[str] = mapped_column(String(30))
    top: Mapped[bool] = mapped_column(Boolean, default=False)
    platform: Mapped[str | None] = mapped_column(String(30), nullable=True)
    currency: Mapped[str] = mapped_column(String(3))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    priority: Mapped[int] = mapped_column(Integer, default=3)
    last_scrape: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    scrape_status: Mapped[str] = mapped_column(String(20), default="pending")
    blocked_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_count: Mapped[int] = mapped_column(Integer, default=0)

    instruments: Mapped[list["Instrument"]] = relationship(back_populates="site")


class Instrument(Base):
    __tablename__ = "instruments"

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"))
    name: Mapped[str] = mapped_column(String(255))
    brand: Mapped[str | None] = mapped_column(String(100), nullable=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    price_current: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    price_eur_equivalent: Mapped[float | None] = mapped_column(Float, nullable=True)
    url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    reviews: Mapped[int] = mapped_column(Integer, default=0)
    stock: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    site: Mapped["Site"] = relationship(back_populates="instruments")

    __table_args__ = (
        Index("ix_instr_name_brand", "name", "brand"),
        Index("ix_instr_site_category", "site_id", "category"),
        Index("ix_instr_updated", "updated_at"),
    )
