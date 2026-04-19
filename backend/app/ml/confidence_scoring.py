"""Steps h & i: Raw confidence scoring + Confidence Adjustment Factor (CAF)."""
from datetime import date

from app.ml.comparables import ComparableRecord


def compute_raw_confidence(
    comps: list[ComparableRecord],
    radius_m: int,
    reference_date: date,
) -> float:
    """
    Score based on:
    - n_comps: number of comparables found
    - Recency: how recent the comparables are
    - Geographic tightness: how close they are
    Returns a score in [0, 1].
    """
    n = len(comps)
    if n == 0:
        return 0.1

    # n_comps score
    if n >= 12:
        n_score = 1.0
    elif n >= 8:
        n_score = 0.9
    elif n >= 4:
        n_score = 0.75
    else:
        n_score = 0.6

    # Recency score: penalise if any comp is > 18 months old
    ages_months = [(reference_date - c.date_of_sale).days / 30.44 for c in comps]
    max_age = max(ages_months) if ages_months else 0
    if max_age <= 6:
        recency_score = 1.0
    elif max_age <= 12:
        recency_score = 0.85
    elif max_age <= 18:
        recency_score = 0.8
    else:
        recency_score = 0.6

    # Geographic score
    if radius_m <= 500:
        geo_score = 1.0
    elif radius_m <= 1000:
        geo_score = 0.9
    elif radius_m <= 2000:
        geo_score = 0.8
    else:
        geo_score = 0.65

    raw = (n_score * 0.5) + (recency_score * 0.3) + (geo_score * 0.2)
    return round(raw, 3)


CAF_FLOOR = 0.30
CAF_CEILING = 0.95


def compute_caf(raw_confidence: float) -> float:
    """
    Confidence Adjustment Factor: shrinks confidence toward centre.
    CAF = 0.3 + 0.65 * raw_confidence  (floor 0.3, ceiling 0.95)
    """
    caf = CAF_FLOOR + 0.65 * raw_confidence
    return round(max(CAF_FLOOR, min(CAF_CEILING, caf)), 3)
