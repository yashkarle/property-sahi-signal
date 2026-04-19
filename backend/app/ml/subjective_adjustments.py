"""Our key differentiator vs BuyerEdge: subjective quality adjustments.

BuyerEdge explicitly states it does NOT incorporate renovation quality, aspect,
garden condition, or internal layout. We do — via user inputs after viewing.
"""


RENOVATION_ADJ = {"basic": -0.03, "standard": 0.0, "premium": 0.05}
ASPECT_ADJ = {"south": 0.02, "south_east": 0.015, "east": 0.005, "north": -0.02, "other": 0.0}
LAYOUT_ADJ = {"poor": -0.03, "standard": 0.0, "excellent": 0.03}
BER_ADJ = {
    "A1": 0.04, "A2": 0.03, "A3": 0.02, "B1": 0.01,
    "B2": 0.0, "B3": -0.01,
    "C1": -0.015, "C2": -0.02, "C3": -0.025,
    "D1": -0.03, "D2": -0.035,
    "E1": -0.04, "E2": -0.045,
    "F": -0.05, "G": -0.06,
}
HEATING_ADJ = {
    "electric_storage": -0.05,  # strongly penalised in Dublin market
    "gas": 0.0,
    "oil": -0.01,
    "heat_pump": 0.02,
    "unknown": 0.0,
}
FIRE_SAFETY_ADJ = -0.03  # Celtic Tiger era (2000-2008) with unresolved cert


def compute_adjustment_factor(
    renovation_standard: str = "standard",
    aspect: str = "other",
    layout_quality: str = "standard",
    ber_rating: str | None = None,
    heating_type: str | None = None,
    is_celtic_tiger_era: bool = False,
    has_fire_cert: bool = True,
) -> tuple[float, dict]:
    """
    Returns (total_adjustment_factor, breakdown_dict).
    Factor is multiplicative: apply to fair_value.
    E.g. 1.05 = 5% upward adjustment; 0.95 = 5% downward.
    """
    breakdown: dict[str, float] = {}

    r_adj = RENOVATION_ADJ.get(renovation_standard, 0.0)
    breakdown["renovation"] = r_adj

    a_adj = ASPECT_ADJ.get(aspect, 0.0)
    breakdown["aspect"] = a_adj

    l_adj = LAYOUT_ADJ.get(layout_quality, 0.0)
    breakdown["layout"] = l_adj

    b_adj = 0.0
    if ber_rating:
        ber_key = ber_rating.upper().replace(" ", "")
        b_adj = BER_ADJ.get(ber_key, 0.0)
    breakdown["ber"] = b_adj

    h_adj = 0.0
    if heating_type:
        h_adj = HEATING_ADJ.get(heating_type, 0.0)
    breakdown["heating"] = h_adj

    fs_adj = 0.0
    if is_celtic_tiger_era and not has_fire_cert:
        fs_adj = FIRE_SAFETY_ADJ
    breakdown["fire_safety"] = fs_adj

    total_pct = r_adj + a_adj + l_adj + b_adj + h_adj + fs_adj
    factor = 1.0 + total_pct
    return round(factor, 4), breakdown
