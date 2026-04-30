"""Property Price Register (PPR) scraper.

The PPR site is a Domino (IBM Lotus Notes) web app. The download requires:
  1. GET the form page to establish a session cookie
  2. Parse the <form> to discover the real action URL and field names
  3. POST the form with Year/County/Month filled in → returns CSV bytes

CSV columns:
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
from bs4 import BeautifulSoup

logger = structlog.get_logger()

PPR_FORM_URL = (
    "https://www.propertypriceregister.ie/website/npsra/pprweb.nsf/PPRDownloads?OpenForm="
)
PPR_BASE = "https://www.propertypriceregister.ie"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-IE,en;q=0.9",
    "Referer": "https://www.propertypriceregister.ie/",
}


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
    """Two-step Domino form submission: GET form → POST with year → parse CSV."""
    async with httpx.AsyncClient(
        timeout=60.0, follow_redirects=True, verify=False, headers=_HEADERS
    ) as client:
        # Step 1: GET the form to get session cookie + real form action
        try:
            form_resp = await client.get(PPR_FORM_URL)
        except Exception as exc:
            logger.debug("ppr_form_get_failed", error=str(exc))
            return []

        if form_resp.status_code != 200:
            logger.debug("ppr_form_get_bad_status", status=form_resp.status_code)
            return []

        soup = BeautifulSoup(form_resp.content, "lxml")
        form = soup.find("form")
        if not form:
            logger.debug("ppr_no_form_in_response", year=year)
            return []

        # Resolve form action URL
        action = form.get("action", PPR_FORM_URL)
        if action.startswith("/"):
            action = PPR_BASE + action
        elif not action.startswith("http"):
            action = PPR_BASE + "/" + action

        # Collect all default field values, then override year/county/month
        post_data: dict[str, str] = {}
        for tag in form.find_all(["input", "select", "textarea"]):
            name = tag.get("name")
            if not name:
                continue
            if tag.name == "select":
                selected = tag.find("option", selected=True)
                post_data[name] = selected["value"] if selected else (
                    tag.find("option")["value"] if tag.find("option") else ""
                )
            elif tag.get("type", "").lower() in ("checkbox", "radio"):
                if tag.get("checked"):
                    post_data[name] = tag.get("value", "on")
            else:
                post_data[name] = tag.get("value", "")

        post_data["Year"] = str(year)
        post_data["County"] = "ALL"
        post_data["Month"] = "ALL"

        logger.debug("ppr_form_post", action=action, year=year)

        # Step 2: POST the form
        try:
            csv_resp = await client.post(action, data=post_data)
        except Exception as exc:
            logger.debug("ppr_form_post_failed", error=str(exc))
            return []

        if csv_resp.status_code != 200:
            logger.debug("ppr_post_bad_status", status=csv_resp.status_code, year=year)
            return []

        preview = csv_resp.content[:512]
        if b"<html" in preview.lower() or b"<!doctype" in preview.lower():
            logger.debug(
                "ppr_post_returned_html",
                year=year,
                status=csv_resp.status_code,
                preview=preview[:200].decode("latin-1", errors="replace"),
            )
            return []

        logger.info("ppr_csv_ok", year=year, bytes=len(csv_resp.content))

    content = csv_resp.content.decode("latin-1")
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

    return PPRRecord(
        address=address,
        eircode=_extract_eircode(address),
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
    return [
        r for r in records
        if "Dublin" in r.county or (r.eircode and r.eircode[:1] == "D")
    ]
