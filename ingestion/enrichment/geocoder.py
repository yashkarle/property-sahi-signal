"""Address → lat/lng geocoding using Google Maps Geocoding API."""
from __future__ import annotations

import os
from typing import Any

import httpx

GOOGLE_MAPS_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")
GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"

DUBLIN_DISTRICT_MAP = {
    "D01": "D1", "D02": "D2", "D03": "D3", "D04": "D4", "D06": "D6", "D06W": "D6W",
    "D07": "D7", "D08": "D8", "D09": "D9", "D10": "D10", "D11": "D11", "D12": "D12",
    "D13": "D13", "D14": "D14", "D15": "D15", "D16": "D16", "D17": "D17", "D18": "D18",
    "D20": "D20", "D22": "D22", "D24": "D24",
}


async def geocode_address(address: str) -> dict[str, Any]:
    if not GOOGLE_MAPS_KEY:
        return {"latitude": None, "longitude": None, "dublin_district": None}

    query = f"{address}, Dublin, Ireland"
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(GEOCODE_URL, params={"address": query, "key": GOOGLE_MAPS_KEY})
        data = resp.json()

    if data.get("status") != "OK" or not data.get("results"):
        return {"latitude": None, "longitude": None, "dublin_district": None}

    location = data["results"][0]["geometry"]["location"]
    lat = location["lat"]
    lng = location["lng"]
    district = _extract_district(data["results"][0], address)

    return {"latitude": lat, "longitude": lng, "dublin_district": district}


def _extract_district(geocode_result: dict, address: str) -> str | None:
    # Try to match eircode prefix from address
    import re
    eircode_match = re.search(r"\b(D\d{2}W?)\b", address.upper())
    if eircode_match:
        prefix = eircode_match.group(1)
        return DUBLIN_DISTRICT_MAP.get(prefix)

    # Try from address components
    for component in geocode_result.get("address_components", []):
        name = component.get("long_name", "").upper()
        if name.startswith("DUBLIN "):
            district = name.replace("DUBLIN ", "D")
            if district in DUBLIN_DISTRICT_MAP.values():
                return district
    return None
