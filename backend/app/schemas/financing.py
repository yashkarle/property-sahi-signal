from pydantic import BaseModel, Field


class ClosingCosts(BaseModel):
    stamp_duty: int
    solicitor_fee: int
    surveyor_fee: int
    valuation_fee: int
    total: int

    @classmethod
    def calculate(cls, price: int) -> "ClosingCosts":
        stamp_duty = round(price * 0.01)
        solicitor = 2500   # solicitor + land registry
        surveyor = 1000    # structural survey
        valuation = 1000   # bank valuation + land registry fees
        return cls(
            stamp_duty=stamp_duty,
            solicitor_fee=solicitor,
            surveyor_fee=surveyor,
            valuation_fee=valuation,
            total=stamp_duty + solicitor + surveyor + valuation,
        )


class FinancingInputs(BaseModel):
    property_price: int = Field(..., gt=0)
    aip_amount: int = Field(..., gt=0, description="Approved In Principle mortgage amount")
    current_savings: int = Field(..., ge=0)
    is_first_time_buyer: bool = True
    timeline_weeks: list[int] = Field(default=[4, 6, 8, 10, 12])
    monthly_savings_rate: int = Field(default=0, ge=0)


class FinancingScenario(BaseModel):
    timeline_weeks: int
    savings_at_close: int
    total_available: int
    deposit_required: int
    closing_costs: int
    total_needed: int
    shortfall: int
    probability_of_success: float
    notes: str


class FinancingSimulationResponse(BaseModel):
    property_price: int
    closing_costs: ClosingCosts
    scenarios: list[FinancingScenario]
    recommendation: str
