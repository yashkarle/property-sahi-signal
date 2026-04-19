"""Step j: Active supply and months supply calculation."""
from datetime import date, timedelta

from app.ml.comparables import ComparableRecord


def compute_supply_metrics(
    active_count: int,
    ppr_sales: list[ComparableRecord],
    reference_date: date,
    window_months: int = 3,
) -> dict[str, float | int]:
    """
    active_count: number of currently active listings in the area
    ppr_sales: comparables used (proxy for demand/sold rate)
    Returns {active_supply_count, monthly_sold_rate, months_supply}
    """
    cutoff = reference_date - timedelta(days=window_months * 30)
    recent_sold = sum(1 for c in ppr_sales if c.date_of_sale >= cutoff)
    monthly_sold_rate = recent_sold / max(window_months, 1)

    if monthly_sold_rate > 0:
        months_supply = round(active_count / monthly_sold_rate, 1)
    else:
        months_supply = 12.0  # assume balanced if no data

    return {
        "active_supply_count": active_count,
        "monthly_sold_rate": round(monthly_sold_rate, 1),
        "months_supply": months_supply,
    }
