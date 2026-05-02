"""Step n: applyFinalConstraints — buyer-specific hard limits and rounding."""


def apply_final_constraints(
    entry: int,
    sealed: int,
    ceiling: int,
    buyer_aip: int | None = None,
    buyer_savings: int | None = None,
    asking_price: int | None = None,
    sealed_bid_probability: float = 0.0,
) -> dict[str, int]:
    """
    1. Ceiling = min(Ceiling, buyer_ceiling) where buyer_ceiling = AIP + savings - closing_costs
    2. If sealed_bid_prob > 50%: Entry ≥ P50 (already applied in offer_band.py)
    3. Round all to nearest €2,500
    4. Ensure entry ≤ sealed ≤ ceiling
    """
    if buyer_aip is not None and buyer_savings is not None:
        closing_costs = round(min(ceiling, asking_price or ceiling) * 0.01) + 4500  # 1% stamp + €2.5k sol + €1k land reg + €1k survey/val
        buyer_ceiling = buyer_aip + buyer_savings - closing_costs
        ceiling = min(ceiling, buyer_ceiling)

    # Round to nearest €2,500
    entry = _round_2500(entry)
    sealed = _round_2500(sealed)
    ceiling = _round_2500(ceiling)

    # Ensure ordering: entry ≤ sealed ≤ ceiling
    sealed = min(sealed, ceiling)
    entry = min(entry, sealed)

    return {"entry": entry, "sealed": sealed, "ceiling": ceiling}


def _round_2500(value: int) -> int:
    return round(value / 2500) * 2500
