"""Property Price Register (PPR) scraper.

Download form URL (discovered from PPR website):
  https://www.propertypriceregister.ie/website/npsra/pprweb.nsf/PPRDownloads
    ?OpenForm=&File=PPR-{year}.csv&County=ALL&Year={year}&Month=ALL

CSV columns (actual PPR format):
Date of Sale (dd/mm/yyyy), Address, Postal Code, County, Price (€),
Not Full Market Price, VAT Exclusive, Description of Property, Property Size Description
"""
from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

import httpx
import structlog

logger = structlog.get_logger()

# Query-string download — works for all available years; County=ALL, Month=ALL = full year
PPR_DOWNLOAD_URL = (
    "https://www.propertypriceregister.ie/website/npsra/pprweb.nsf/PPRDownloads"
    "?OpenForm=&File=PPR-{year}.csv&County=ALL&Year={year}&Month=ALL"
)


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
    """Download the full-year PPR CSV for the given year; return [] if unavailable."""
    url = PPR_DOWNLOAD_URL.format(year=year)
    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True, verify=False) as client:
        try:
            resp = await client.get(url)
        except Exception as exc:
            logger.debug("ppr_url_failed", url=url, error=str(exc))
            return []

        if resp.status_code != 200:
            logger.debug("ppr_url_bad_status", url=url, status=resp.status_code)
            return []

        # Verify we got CSV not an HTML error page
        preview = resp.content[:512]
        if b"<html" in preview.lower() or b"<!doctype" in preview.lower():
            logger.debug(
                "ppr_url_returned_html",
                url=url,
                preview=preview[:200].decode("latin-1", errors="replace"),
            )
            return []

        logger.info("ppr_url_ok", url=url, bytes=len(resp.content))

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
