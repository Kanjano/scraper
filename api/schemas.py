"""Pydantic response/request models."""
from pydantic import BaseModel


class OfferOut(BaseModel):
    rank: int
    site: str | None = None
    site_key: str | None = None
    area: str | None = None
    country: str | None = None
    name: str | None = None
    price: float | None = None
    currency: str | None = None
    price_eur: float | None = None
    rating: float | None = None
    url: str | None = None
    data_quality: str | None = None
    is_accessory: bool = False
    image: str | None = None
    original_price: float | None = None      # before the discount, shop currency
    original_price_eur: float | None = None
    discount_pct: int = 0                    # 0 = not on sale
    relevance: float = 0.0                   # 0..1, fit to the query
    discount_everywhere: bool = False        # the shop shows a cut on nearly all it sold: a list price


class SearchResponse(BaseModel):
    query: str
    translated_query: str | None = None
    sites_queried: int = 0
    total_results: int
    lowest_price: float | None = None
    lowest_price_site: str | None = None
    market_average: float | None = None
    results: list[OfferOut]
    search_time_seconds: float


class PricingRequestOffer(BaseModel):
    site: str
    price_eur: float
    reviews: int = 0
    stock: int | None = None


class PricingResponse(BaseModel):
    price_suggested: float
    margin_percentage: float
    margin_amount: float
    lowest_price_site: str
    lowest_price: float
    market_average: float
    total_sites_analyzed: int
    reasoning: str


class SiteStatus(BaseModel):
    site_key: str
    name: str
    area: str
    group: str
    country: str
    city: str | None = None
    specialty: str
    type: str
    top: bool
    platform: str | None = None
    currency: str
    searchable: bool
    enabled: bool
    priority: int
    data_quality: str | None = None
    blocked_reason: str | None = None
    last_scrape: str | None = None
    scrape_status: str
    error_count: int
