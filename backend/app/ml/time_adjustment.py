"""Step e: €/m² trend computation and time-adjustment of comparable prices."""
from datetime import date

import numpy as np

from app.ml.comparables import ComparableRecord


def compute_monthly_drift(comps_with_area: list[ComparableRecord], reference_date: date) -> float:
    """
    Compute monthly price drift rate from comparables that have floor_area_sqm.
    Returns monthly drift as a fraction (e.g. 0.005 = 0.5%/month appreciation).
    Falls back to 0.003 (0.3%/mo) if insufficient data — typical Dublin 2024-2026.
    """
    points = []
    for c in comps_with_area:
        if not c.floor_area_sqm or not c.price_eur:
            continue
        months_ago = (reference_date - c.date_of_sale).days / 30.44
        ppsqm = c.price_eur / c.floor_area_sqm
        points.append((months_ago, ppsqm))

    if len(points) < 3:
        return 0.003  # default: 0.3%/month Dublin appreciation

    months = np.array([p[0] for p in points])
    prices = np.array([p[1] for p in points])
    # Simple OLS: price = a + b * months_ago  →  recent prices should be higher
    try:
        coeffs = np.polyfit(months, prices, 1)
        median_price = np.median(prices)
        drift_per_month = -coeffs[0] / max(median_price, 1)  # negative because months_ago
        return float(np.clip(drift_per_month, -0.02, 0.02))
    except Exception:
        return 0.003


def time_adjust_prices(
    comps: list[ComparableRecord],
    monthly_drift: float,
    reference_date: date,
) -> list[tuple[ComparableRecord, int]]:
    """
    Returns (comparable, time_adjusted_price_eur) list.
    Formula: adjusted = original * (1 + monthly_drift)^months_ago
    """
    adjusted = []
    for comp in comps:
        months_ago = (reference_date - comp.date_of_sale).days / 30.44
        factor = (1 + monthly_drift) ** months_ago
        adj_price = round(comp.price_eur * factor)
        adjusted.append((comp, adj_price))
    return adjusted
