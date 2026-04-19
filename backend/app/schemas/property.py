import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class NeighbourhoodScoreOut(BaseModel):
    safety_score: float | None = None
    amenities_score: float | None = None
    connectivity_score: float | None = None
    schools_score: float | None = None
    parks_score: float | None = None
    cafes_score: float | None = None
    supermarkets_score: float | None = None
    m50_n11_score: float | None = None
    overall_score: float | None = None
    commute_dundrum_min: float | None = None
    computed_at: datetime | None = None


class PropertySummary(BaseModel):
    id: uuid.UUID
    url: str
    title: str | None = None
    address: str | None = None
    dublin_district: str | None = None
    price: int | None = None
    bedrooms: int | None = None
    bathrooms: int | None = None
    carpet_area_sqm: int | None = None
    property_type: str | None = None
    ber_rating: str | None = None
    heating_type: str | None = None
    is_chain_free: bool | None = None
    is_south_facing: bool | None = None
    is_htb_eligible: bool | None = None
    days_on_market: int | None = None
    estate_agent: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    is_active: bool = True
    missing_data_flags: list[str] | None = None

    model_config = {"from_attributes": True}


class PropertyDetail(PropertySummary):
    eircode: str | None = None
    year_built: int | None = None
    management_fee_eur: int | None = None
    seller_status: str | None = None
    description: str | None = None
    features_list: list[str] | None = None
    price_history: list[dict] | None = None
    neighbourhood_score: NeighbourhoodScoreOut | None = None


class CompareRequest(BaseModel):
    property_ids: list[uuid.UUID] = Field(..., min_length=2, max_length=3)


class CompareResponse(BaseModel):
    summary: str
    properties: list[PropertySummary]
    comparison_table: dict
