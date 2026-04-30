"""Convert PPRRecord → dict ready for ppr_sales Postgres upsert."""
from __future__ import annotations

import re

from ingestion.scrapers.ppr_scraper import PPRRecord

EIRCODE_PREFIX_TO_DISTRICT = {
    "D01": "D1", "D02": "D2", "D03": "D3", "D04": "D4",
    "D06": "D6", "D6W": "D6W", "D07": "D7", "D08": "D8",
    "D09": "D9", "D10": "D10", "D11": "D11", "D12": "D12",
    "D13": "D13", "D14": "D14", "D15": "D15", "D16": "D16",
    "D17": "D17", "D18": "D18", "D20": "D20", "D22": "D22", "D24": "D24",
}

SUBURB_TO_DISTRICT = {
    "crumlin": "D12", "walkinstown": "D12", "perrystown": "D12",
    "kimmage": "D6W", "terenure": "D6W", "harold's cross": "D6W",
    "rathmines": "D6", "ranelagh": "D6", "rathgar": "D6",
    "clontarf": "D3", "ballsbridge": "D4", "donnybrook": "D4",
    "sandymount": "D4", "ringsend": "D4",
    "drumcondra": "D9", "glasnevin": "D9", "finglas": "D11",
    "blanchardstown": "D15", "castleknock": "D15",
    "lucan": "D20", "palmerstown": "D20",
    "tallaght": "D24", "rathfarnham": "D16",
    "dundrum": "D14", "stillorgan": "D18",
    "blackrock": "D18", "dun laoghaire": "D18",
}

DISTRICT_RE = re.compile(r"\bDublin[\s,]+(\d+[WX]?)\b", re.IGNORECASE)


def parse_ppr_record(record: PPRRecord, source_file: str = "") -> dict:
    district = _derive_district(record.eircode, record.address)
    return {
        "address": record.address,
        "eircode": record.eircode,
        "county": record.county,
        "date_of_sale": record.date_of_sale.isoformat(),
        "price_eur": record.price_eur,
        "not_full_market_price": record.not_full_market_price,
        "vat_exclusive": record.vat_exclusive,
        "property_description": record.property_description,
        "dublin_district": district,
        "source_file": source_file or "ppr",
        "latitude": None,
        "longitude": None,
        "floor_area_sqm": None,
        "price_per_sqm": None,
        "bedrooms": None,
        "property_type": None,
        "matched_property_id": None,
    }


def _derive_district(eircode: str | None, address: str) -> str | None:
    # From eircode prefix
    if eircode:
        prefix = eircode[:3].upper()
        if prefix in EIRCODE_PREFIX_TO_DISTRICT:
            return EIRCODE_PREFIX_TO_DISTRICT[prefix]
        # D6W special case
        if eircode.upper().startswith("D6W"):
            return "D6W"

    # From "Dublin X" pattern in address
    m = DISTRICT_RE.search(address)
    if m:
        return f"D{m.group(1).upper()}"

    # From suburb name
    address_lower = address.lower()
    for suburb, district in SUBURB_TO_DISTRICT.items():
        if suburb in address_lower:
            return district

    return None
