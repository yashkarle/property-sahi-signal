import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class BidSessionCreate(BaseModel):
    property_id: uuid.UUID
    user_max_budget: int = Field(..., gt=0)


class BidEntryCreate(BaseModel):
    bid_amount: int = Field(..., gt=0)
    submitted_by: str = Field(..., pattern="^(user|other_buyer)$")
    notes: str | None = None


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
    strategy_advice: str | None = None
    started_at: datetime
    entries: list[BidEntryOut] = []

    model_config = {"from_attributes": True}


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
