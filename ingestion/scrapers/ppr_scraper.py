"""Property Price Register (PPR) scraper.

The PPR publishes monthly CSV files at:
https://www.propertypriceregister.ie/website/npsra/pprweb.nsf/Downloads/PPR-{YEAR}.csv

CSV columns (actual PPR format):
Date of Sale (dd/mm/yyyy), Address, Postal Code, County, Price (€),
Not Full Market Price, VAT Exclusive, Description of Property, Property Size Description
"""
import csv
import io
import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

import httpx

PPR_BASE_URL = "https://www.propertypriceregister.ie/website/npsra/pprweb.nsf/Downloads/PPR-{year}.csv/$FILE/PPR-{year}.csv"


@dataclass
class PPRRecord:
    address: str
    eircode: str | None
    county: str
    date_of_sale: date
    price_eur: int
    not_full_market_price: bool
    vat_exclusive: bool
    property_description: str


async def download_ppr_csv(year: int) -> list[PPRRecord]:
    url = PPR_BASE_URL.format(year=year)
    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()

    # PPR CSV uses latin-1 encoding
    content = resp.content.decode("latin-1")
    reader = csv.DictReader(io.StringIO(content))
    records = []
    for row in reader:
        try:
            record = _parse_row(row)
            if record:
                records.append(record)
        except Exception:
            continue
    return records


def _parse_row(row: dict[str, str]) -> PPRRecord | None:
    date_str = row.get("Date of Sale (dd/mm/yyyy)", "").strip()
    if not date_str:
        return None
    try:
        sale_date = datetime.strptime(date_str, "%d/%m/%Y").date()
    except ValueError:
        return None

    price_str = row.get("Price (€)", "0").strip().replace("€", "").replace(",", "").strip()
    try:
        price = int(float(price_str))
    except ValueError:
        return None

    if price <= 0:
        return None

    address = row.get("Address", "").strip()
    county = row.get("County", "").strip()

    # Extract eircode if present in address
    eircode = _extract_eircode(address)

    return PPRRecord(
        address=address,
        eircode=eircode,
        county=county,
        date_of_sale=sale_date,
        price_eur=price,
        not_full_market_price=row.get("Not Full Market Price", "No").strip().lower() == "yes",
        vat_exclusive=row.get("VAT Exclusive", "No").strip().lower() == "yes",
        property_description=row.get("Description of Property", "").strip(),
    )


EIRCODE_RE = re.compile(r"\b([A-Z]\d{2}\s?[A-Z0-9]{4})\b", re.IGNORECASE)


def _extract_eircode(address: str) -> str | None:
    match = EIRCODE_RE.search(address)
    if match:
        return match.group(1).upper().replace(" ", "")
    return None


def filter_dublin_records(records: list[PPRRecord]) -> list[PPRRecord]:
    """Filter to Dublin county records only."""
    return [
        r for r in records
        if "Dublin" in r.county or (r.eircode and r.eircode[:1] == "D")
    ]
