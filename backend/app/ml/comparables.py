"""Step c: Geographic + temporal comparable ladder.

Start at 500m / 3-month window and expand until ≥8 comparables are found.
Falls back to wider searches up to 5km / 24 months.
"""
from dataclasses import dataclass
from datetime import date, timedelta
from math import asin, cos, radians, sin, sqrt
from typing import Any


@dataclass
class ComparableRecord:
    id: str
    address: str
    date_of_sale: date
    price_eur: int
    floor_area_sqm: int | None
    price_per_sqm: float | None
    bedrooms: int | None
    property_type: str | None
    latitude: float
    longitude: float
    matched_property_id: str | None = None


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine distance in metres."""
    R = 6_371_000
    phi1, phi2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlambda = radians(lon2 - lon1)
    a = sin(dphi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(dlambda / 2) ** 2
    return 2 * R * asin(sqrt(a))


LADDER_STEPS = [
    (500, 3),
    (1000, 6),
    (2000, 12),
    (5000, 24),
]
MIN_COMPARABLES = 8


def select_comparables(
    target_lat: float,
    target_lon: float,
    target_eircode_prefix: str | None,
    all_ppr_sales: list[Any],
    reference_date: date | None = None,
) -> tuple[list[ComparableRecord], int, int]:
    """
    Returns (selected_comparables, final_radius_m, final_window_months).
    all_ppr_sales: list of PPRSale ORM objects or dicts with lat/lon/date_of_sale.
    """
    ref = reference_date or date.today()

    for radius_m, months in LADDER_STEPS:
        cutoff = ref - timedelta(days=months * 30)
        candidates = []
        for sale in all_ppr_sales:
            lat = float(getattr(sale, "latitude", 0) or 0)
            lon = float(getattr(sale, "longitude", 0) or 0)
            if not lat or not lon:
                continue
            dist = haversine_m(target_lat, target_lon, lat, lon)
            if dist > radius_m:
                continue
            sale_date = getattr(sale, "date_of_sale", None)
            if not sale_date or sale_date < cutoff:
                continue

            candidates.append(ComparableRecord(
                id=str(getattr(sale, "id", "")),
                address=getattr(sale, "address", ""),
                date_of_sale=sale_date,
                price_eur=int(getattr(sale, "price_eur", 0)),
                floor_area_sqm=getattr(sale, "floor_area_sqm", None),
                price_per_sqm=float(getattr(sale, "price_per_sqm", 0) or 0) or None,
                bedrooms=getattr(sale, "bedrooms", None),
                property_type=getattr(sale, "property_type", None),
                latitude=lat,
                longitude=lon,
                matched_property_id=str(getattr(sale, "matched_property_id", "") or ""),
            ))

        if len(candidates) >= MIN_COMPARABLES:
            # Sort by distance then recency
            candidates.sort(key=lambda c: haversine_m(target_lat, target_lon, c.latitude, c.longitude))
            return candidates, radius_m, months

    # Return whatever we have at the widest step
    all_candidates = []
    for sale in all_ppr_sales:
        lat = float(getattr(sale, "latitude", 0) or 0)
        lon = float(getattr(sale, "longitude", 0) or 0)
        if lat and lon:
            all_candidates.append(ComparableRecord(
                id=str(getattr(sale, "id", "")),
                address=getattr(sale, "address", ""),
                date_of_sale=getattr(sale, "date_of_sale", date.today()),
                price_eur=int(getattr(sale, "price_eur", 0)),
                floor_area_sqm=getattr(sale, "floor_area_sqm", None),
                price_per_sqm=float(getattr(sale, "price_per_sqm", 0) or 0) or None,
                bedrooms=getattr(sale, "bedrooms", None),
                property_type=getattr(sale, "property_type", None),
                latitude=lat,
                longitude=lon,
            ))
    all_candidates.sort(key=lambda c: haversine_m(target_lat, target_lon, c.latitude, c.longitude))
    return all_candidates[:20], 5000, 24
