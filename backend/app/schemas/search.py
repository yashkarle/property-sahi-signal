from pydantic import BaseModel, Field


class SearchFilters(BaseModel):
    price_min: int | None = None
    price_max: int | None = None
    bedrooms_min: int | None = None
    bathrooms_min: int | None = None
    carpet_area_sqm_min: int | None = None
    property_types: list[str] | None = None
    ber_ratings: list[str] | None = None
    heating_types: list[str] | None = None
    dublin_districts: list[str] | None = None
    is_chain_free: bool | None = None
    is_htb_eligible: bool | None = None
    days_on_market_max: int | None = None
    exclude_electric_storage: bool = False
    exclude_celtic_tiger: bool = False


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=512)
    filters: SearchFilters = Field(default_factory=SearchFilters)
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class SearchResponse(BaseModel):
    results: list
    total: int
    search_id: str
    query_time_ms: float
