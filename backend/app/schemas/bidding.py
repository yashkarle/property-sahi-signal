import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class BidSessionCreate(BaseModel):
    property_id: uuid.UUID
    user_max_budget: int = Field(..., gt=0)  # kept for compat — set to user_aip when provided
    user_aip: int | None = Field(None, gt=0, description="Approved In Principle mortgage amount")
    user_savings: int | None = Field(None, ge=0, description="Available cash savings")


class BidEntryCreate(BaseModel):
    bid_amount: int = Field(..., gt=0)
    submitted_by: str = Field(..., pattern="^(user|other_buyer)$")
    notes: str | None = None


class OutcomeUpdate(BaseModel):
    outcome: str = Field(..., pattern="^(won|lost|withdrawn)$")
    actual_sale_price: int | None = Field(None, gt=0)


class BidEntryOut(BaseModel):
    id: uuid.UUID
    bid_amount: int
    submitted_by: str
    submitted_at: datetime
    notes: str | None = None
    is_winning: bool

    model_config = {"from_attributes": True}


class BidSessionOut(BaseModel):
    id: uuid.UUID
    property_id: uuid.UUID
    status: str
    user_max_budget: int | None = None
    user_aip: int | None = None
    user_savings: int | None = None
    actual_sale_price: int | None = None
    strategy_advice: str | None = None
    started_at: datetime
    entries: list[BidEntryOut] = []

    model_config = {"from_attributes": True}


class PropertySummaryForHistory(BaseModel):
    id: uuid.UUID
    address: str | None = None
    price: int | None = None
    bedrooms: int | None = None
    carpet_area_sqm: int | None = None
    ber_rating: str | None = None
    dublin_district: str | None = None
    url: str

    model_config = {"from_attributes": True}


class PriceModelSummary(BaseModel):
    offer_entry: int | None = None
    offer_sealed: int | None = None
    p25: int | None = None
    p50: int | None = None
    sealed_bid_probability: float | None = None


class BidHistoryItem(BaseModel):
    session_id: uuid.UUID
    property: PropertySummaryForHistory
    status: str
    user_max_budget: int | None = None
    user_aip: int | None = None
    user_savings: int | None = None
    started_at: datetime
    your_max_bid: int | None = None
    competing_max_bid: int | None = None
    actual_sale_price: int | None = None
    latest_price_model: PriceModelSummary | None = None


class OfferBandOut(BaseModel):
    entry: int
    sealed: int
    ceiling: int
    seller_leverage_score: float | None = None
    sealed_bid_probability: float | None = None
    over_asking_probability: float | None = None
    confidence_final: float | None = None
    p25: int | None = None
    p50: int | None = None
    p75: int | None = None


class BidLetterRequest(BaseModel):
    user_bid: int
    competing_bid: int | None = None
    additional_context: str | None = None


class BidLetterResponse(BaseModel):
    letter_text: str
