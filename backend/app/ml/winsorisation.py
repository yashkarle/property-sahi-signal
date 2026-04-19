"""Step f: P10/P90 winsorisation and size-adjusted fair value."""
import numpy as np

from app.ml.comparables import ComparableRecord


def winsorise_and_size_adjust(
    adjusted_comps: list[tuple[ComparableRecord, int]],
    target_carpet_area_sqm: int | None,
) -> tuple[list[tuple[ComparableRecord, int]], float | None]:
    """
    1. Remove prices below P10 and above P90 (winsorise)
    2. Compute size-adjusted fair value: median(€/sqm) × target area
    Returns (winsorised_comps, size_adjusted_fair_value).
    """
    if not adjusted_comps:
        return [], None

    prices = np.array([p for _, p in adjusted_comps])
    p10 = float(np.percentile(prices, 10))
    p90 = float(np.percentile(prices, 90))

    winsorised = [(c, p) for c, p in adjusted_comps if p10 <= p <= p90]
    if not winsorised:
        winsorised = adjusted_comps  # all were outliers — keep all

    # Size-adjusted fair value
    size_adj_value: float | None = None
    if target_carpet_area_sqm:
        price_per_sqm_list = []
        for comp, adj_price in winsorised:
            if comp.floor_area_sqm and comp.floor_area_sqm > 0:
                price_per_sqm_list.append(adj_price / comp.floor_area_sqm)
        if price_per_sqm_list:
            median_ppsqm = float(np.median(price_per_sqm_list))
            size_adj_value = median_ppsqm * target_carpet_area_sqm

    return winsorised, size_adj_value
