"""Analytics endpoints."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from config.database import get_db
from pricing.market_analyzer import MarketAnalyzer

router = APIRouter(tags=["analytics"])


@router.get("/market-analysis")
def market_analysis(db: Session = Depends(get_db)):
    return MarketAnalyzer(db).market_overview()


@router.get("/price-history/{instrument_id}")
def price_history(instrument_id: int, days: int = 30, db: Session = Depends(get_db)):
    return MarketAnalyzer(db).price_trend(instrument_id, days=days)
