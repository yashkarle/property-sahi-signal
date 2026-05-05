import uuid
from datetime import date

from pydantic import BaseModel


class SubjectiveInputs(BaseModel):
    renovation_standard: str = "standard"  # basic | standard | premium
    aspect: str = "other"                  # south | south_east | north | other
    layout_quality: str = "standard"       # poor | standard | excellent
    has_garden: bool = False
    has_balcony: bool = False


class ComparableOut(BaseModel):
    address: str
    date_of_sale: date
    price_eur: int
    floor_area_sqm: int | None = None
    price_per_sqm: float | None = None
    bedrooms: int | None = None
    property_type: str | None = None
    distance_m: float
    months_ago: float
    time_adjusted_price: int | None = None
    latitude: float | None = None
    longitude: float | None = None
    similarity_score: float | None = None


class PricingAnalyseRequest(BaseModel):
    property_id: uuid.UUID
    subjective_inputs: SubjectiveInputs = SubjectiveInputs()
    buyer_aip: int | None = None
    buyer_savings: int | None = None
    is_first_time_buyer: bool = True


class PriceModelResultOut(BaseModel):
    property_id: uuid.UUID
    status: str
    n_comparables: int | None = None
    geographic_radius_m: int | None = None
    temporal_window_months: int | None = None
    size_adjusted_fair_value: int | None = None
    p25_estimate: int | None = None
    p50_estimate: int | None = None
    p75_estimate: int | None = None
    iqr: int | None = None
    confidence_raw: float | None = None
    caf: float | None = None
    confidence_final: float | None = None
    active_supply_count: int | None = None
    months_supply: float | None = None
    seller_leverage_score: float | None = None
    sealed_bid_probability: float | None = None
    over_asking_probability: float | None = None
    offer_entry: int | None = None
    offer_sealed: int | None = None
    offer_ceiling: int | None = None
    buyer_ceiling: int | None = None
    subjective_inputs: dict | None = None
    subjective_adjustment_factor: float | None = None

    model_config = {"from_attributes": True}


class AgentAnalysisRow(BaseModel):
    agent_name: str
    n_sold: int
    total_revenue: int
    avg_price: int
    vs_asking_pct: float
    p75_price: int
    breakdown_by_type: dict[str, int]
