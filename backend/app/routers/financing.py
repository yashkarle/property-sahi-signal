from fastapi import APIRouter

from app.dependencies import AuthDep
from app.schemas.financing import ClosingCosts, FinancingInputs, FinancingSimulationResponse
from app.services.financing_service import simulate_financing

router = APIRouter(prefix="/financing", tags=["financing"])


@router.post("/simulate", response_model=FinancingSimulationResponse)
async def financing_simulation(inputs: FinancingInputs, _: AuthDep) -> FinancingSimulationResponse:
    return simulate_financing(inputs)


@router.get("/closing-costs")
async def closing_costs(price: int, _: AuthDep) -> ClosingCosts:
    return ClosingCosts.calculate(price)
