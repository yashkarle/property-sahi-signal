"""Step d: Similarity scoring with same-development boost."""
from app.ml.comparables import ComparableRecord, haversine_m


def score_comparables(
    target: dict,
    comps: list[ComparableRecord],
    target_eircode_prefix: str | None = None,
) -> list[tuple[ComparableRecord, float]]:
    """
    Returns list of (comparable, score) sorted by score descending.
    Score range 0-1. Same-development comparables get 1.5x boost (capped at 1.0).
    """
    target_beds = target.get("bedrooms")
    target_type = target.get("property_type")
    target_area = target.get("carpet_area_sqm")
    target_lat = target.get("latitude", 0)
    target_lon = target.get("longitude", 0)

    scored = []
    for comp in comps:
        score = 0.0
        factors = 0

        # Bedroom match
        if target_beds and comp.bedrooms:
            bed_diff = abs(target_beds - comp.bedrooms)
            score += max(0.0, 1.0 - bed_diff * 0.3)
            factors += 1

        # Property type match
        if target_type and comp.property_type:
            score += 1.0 if target_type == comp.property_type else 0.3
            factors += 1

        # Size similarity (within 20sqm = full score)
        if target_area and comp.floor_area_sqm:
            size_diff = abs(target_area - comp.floor_area_sqm)
            score += max(0.0, 1.0 - size_diff / 20.0)
            factors += 1

        base_score = score / max(factors, 1)

        # Same-development boost: within 50m = same block
        dist = haversine_m(target_lat, target_lon, comp.latitude, comp.longitude)
        if dist < 50:
            base_score = min(1.0, base_score * 1.5)

        # Same eircode prefix boost
        if target_eircode_prefix and comp.id:
            # If comp address contains same eircode area
            pass

        scored.append((comp, round(base_score, 3)))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored
