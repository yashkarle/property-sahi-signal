import httpx

from app.models.neighbourhood_score import NeighbourhoodScore

OVERPASS_URL = "https://overpass-api.de/api/interpreter"


async def compute_neighbourhood_score(
    lat: float,
    lon: float,
    property_id: str,
) -> NeighbourhoodScore:
    queries = {
        "safety": _query(lat, lon, 2000, '["amenity"="police"]'),
        "amenities": _query(lat, lon, 1000, '["shop"~"supermarket|convenience|chemist|pharmacy"]["amenity"~"clinic|doctors"]'),
        "luas": _query(lat, lon, 800, '["railway"="tram_stop"]'),
        "bus": _query(lat, lon, 400, '["highway"="bus_stop"]'),
        "schools": _query(lat, lon, 1000, '["amenity"~"school|college"]'),
        "parks": _query(lat, lon, 500, '["leisure"~"park|nature_reserve|garden"]'),
        "cafes": _query(lat, lon, 500, '["amenity"~"cafe|restaurant|bar"]'),
        "supermarkets": _query(lat, lon, 1000, '["shop"~"supermarket|discount_supermarket"]'),
        "motorway": _query(lat, lon, 3000, '["highway"~"motorway_junction|motorway"]'),
    }

    counts: dict[str, int] = {}
    async with httpx.AsyncClient(timeout=10.0) as client:
        for name, q in queries.items():
            try:
                resp = await client.post(OVERPASS_URL, data={"data": q})
                data = resp.json()
                counts[name] = len(data.get("elements", []))
            except Exception:
                counts[name] = 0

    connectivity_score = min(10.0, (counts["luas"] * 3 + counts["bus"] * 1) * 1.5)
    score = NeighbourhoodScore(
        property_id=property_id,
        safety_score=min(10.0, counts["safety"] * 5),
        amenities_score=min(10.0, counts["amenities"] * 2),
        connectivity_score=connectivity_score,
        schools_score=min(10.0, counts["schools"] * 3),
        parks_score=min(10.0, counts["parks"] * 3),
        cafes_score=min(10.0, counts["cafes"] * 0.8),
        supermarkets_score=min(10.0, counts["supermarkets"] * 4),
        m50_n11_score=min(10.0, counts["motorway"] * 3),
        data_sources=counts,
    )
    score.overall_score = round(score.compute_overall(), 1)
    return score


def _query(lat: float, lon: float, radius: int, tag_filter: str) -> str:
    return f"""
[out:json][timeout:10];
(
  node{tag_filter}(around:{radius},{lat},{lon});
  way{tag_filter}(around:{radius},{lat},{lon});
);
out count;
"""
