"""Convert DaftListing dataclass → dict ready for Postgres upsert."""
from __future__ import annotations

import re
from datetime import datetime, timezone

from ingestion.scrapers.daft_scraper import DaftListing

HEATING_KEYWORDS = {
    "electric storage": "electric_storage",
    "storage heater": "electric_storage",
    "gas": "gas",
    "oil": "oil",
    "heat pump": "heat_pump",
    "geothermal": "heat_pump",
}

SOUTH_FACING_RE = re.compile(r"south[\s-]?fac", re.IGNORECASE)
CHAIN_FREE_RE = re.compile(r"chain[\s-]?free|no chain|vacant|owner[\s-]?occupi", re.IGNORECASE)
HTB_RE = re.compile(r"help[\s-]?to[\s-]?buy|htb|first[\s-]?time buyer", re.IGNORECASE)
YEAR_BUILT_RE = re.compile(r"built\s+(?:in\s+)?(\d{4})|(\d{4})\s+(?:built|build|construction)", re.IGNORECASE)
MGMT_FEE_RE = re.compile(r"management\s+fee[:\s]+€?([\d,]+)", re.IGNORECASE)


def parse_listing(listing: DaftListing) -> dict:
    """Convert a scraped DaftListing to a Postgres-ready dict."""
    combined_text = f"{listing.title or ''} {listing.description or ''} {' '.join(listing.features)}"

    heating_type = _detect_heating(combined_text)
    is_south_facing = bool(SOUTH_FACING_RE.search(combined_text))
    is_chain_free = bool(CHAIN_FREE_RE.search(combined_text))
    is_htb_eligible = bool(HTB_RE.search(combined_text))

    year_built = _extract_year_built(combined_text)
    management_fee = _extract_management_fee(combined_text)

    missing_flags: list[str] = []
    if not listing.carpet_area_sqm:
        missing_flags.append("carpet_area_sqm")
    if not listing.ber_rating:
        missing_flags.append("ber_rating")
    if not year_built:
        missing_flags.append("year_built")
    if not listing.bathrooms:
        missing_flags.append("bathrooms")

    return {
        "source": "daft",
        "source_id": listing.source_id,
        "url": listing.url,
        "title": listing.title,
        "address": listing.address,
        "price": listing.price,
        "bedrooms": listing.bedrooms,
        "bathrooms": listing.bathrooms,
        "carpet_area_sqm": listing.carpet_area_sqm,
        "property_type": listing.property_type,
        "ber_rating": _normalise_ber(listing.ber_rating),
        "heating_type": heating_type,
        "year_built": year_built,
        "management_fee_eur": management_fee,
        "is_chain_free": is_chain_free,
        "is_south_facing": is_south_facing,
        "is_htb_eligible": is_htb_eligible,
        "estate_agent": listing.estate_agent,
        "description": listing.description,
        "features_list": listing.features or [],
        "missing_data_flags": missing_flags,
        "is_active": True,
        "last_scraped_at": datetime.now(timezone.utc).isoformat(),
    }


def _detect_heating(text: str) -> str | None:
    text_lower = text.lower()
    for keyword, heating_type in HEATING_KEYWORDS.items():
        if keyword in text_lower:
            return heating_type
    return None


def _normalise_ber(ber: str | None) -> str | None:
    if not ber:
        return None
    ber = ber.strip().upper()
    valid = {"A1", "A2", "A3", "B1", "B2", "B3", "C1", "C2", "C3", "D1", "D2", "E1", "E2", "F", "G"}
    if ber in valid:
        return ber
    # Try adding digit: "A" → "A1", "B" → "B1" etc.
    if len(ber) == 1 and ber in "ABCDE":
        candidate = f"{ber}1"
        return candidate if candidate in valid else None
    return None


def _extract_year_built(text: str) -> int | None:
    match = YEAR_BUILT_RE.search(text)
    if match:
        year_str = match.group(1) or match.group(2)
        try:
            year = int(year_str)
            if 1800 <= year <= 2030:
                return year
        except ValueError:
            pass
    return None


def _extract_management_fee(text: str) -> int | None:
    match = MGMT_FEE_RE.search(text)
    if match:
        try:
            return int(match.group(1).replace(",", ""))
        except ValueError:
            pass
    return None
