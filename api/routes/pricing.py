"""Pricing endpoints."""
from fastapi import APIRouter, HTTPException

from api.schemas import PricingRequestOffer, PricingResponse
from pricing import PricingEngine

router = APIRouter(prefix="/pricing", tags=["pricing"])
engine = PricingEngine()


@router.post("", response_model=PricingResponse)
def suggest_price(offers: list[PricingRequestOffer]):
    result = engine.calculate_suggested_price([o.model_dump() for o in offers])
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result
