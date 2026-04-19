import math

from app.schemas.financing import ClosingCosts, FinancingInputs, FinancingScenario, FinancingSimulationResponse


def simulate_financing(inputs: FinancingInputs) -> FinancingSimulationResponse:
    closing = ClosingCosts.calculate(inputs.property_price)
    deposit_required = max(
        inputs.property_price - inputs.aip_amount,
        round(inputs.property_price * 0.10),
    )
    total_needed = deposit_required + closing.total

    scenarios: list[FinancingScenario] = []
    for weeks in inputs.timeline_weeks:
        additional_savings = (weeks // 4) * inputs.monthly_savings_rate
        savings_at_close = inputs.current_savings + additional_savings
        total_available = inputs.aip_amount + savings_at_close
        shortfall = max(0, total_needed - savings_at_close)
        prob = _probability_of_success(savings_at_close, total_needed, shortfall)
        scenarios.append(FinancingScenario(
            timeline_weeks=weeks,
            savings_at_close=savings_at_close,
            total_available=total_available,
            deposit_required=deposit_required,
            closing_costs=closing.total,
            total_needed=total_needed,
            shortfall=shortfall,
            probability_of_success=prob,
            notes=_scenario_note(prob, shortfall),
        ))

    recommendation = _overall_recommendation(scenarios, inputs)
    return FinancingSimulationResponse(
        property_price=inputs.property_price,
        closing_costs=closing,
        scenarios=scenarios,
        recommendation=recommendation,
    )


def _probability_of_success(savings: int, needed: int, shortfall: int) -> float:
    if shortfall <= 0:
        return 1.0
    # Logistic function: 50% probability at shortfall == 10k, drops steeply
    x = -shortfall / 10000
    return round(1 / (1 + math.exp(-x)), 3)


def _scenario_note(prob: float, shortfall: int) -> str:
    if prob >= 0.95:
        return "Comfortable — you have a solid buffer."
    elif prob >= 0.75:
        return f"Feasible with €{shortfall:,} shortfall — bridge with savings discipline."
    elif prob >= 0.5:
        return f"Tight — €{shortfall:,} shortfall requires additional funds or price negotiation."
    else:
        return f"High risk — €{shortfall:,} shortfall. Consider a lower bid or extending timeline."


def _overall_recommendation(scenarios: list[FinancingScenario], inputs: FinancingInputs) -> str:
    best = max(scenarios, key=lambda s: s.probability_of_success)
    worst = min(scenarios, key=lambda s: s.probability_of_success)
    if worst.probability_of_success >= 0.9:
        return f"You can comfortably close at any timeline. Best position at {best.timeline_weeks} weeks."
    elif best.probability_of_success >= 0.75:
        return (
            f"Target {best.timeline_weeks} weeks for strongest position. "
            f"Push for quick close — your chain-free status is your leverage."
        )
    else:
        return (
            f"Finances are stretched at €{inputs.property_price:,}. "
            f"Consider bidding €{inputs.property_price - 10000:,} or asking for €{inputs.property_price - 5000:,} — "
            f"even a small reduction significantly improves your position."
        )
