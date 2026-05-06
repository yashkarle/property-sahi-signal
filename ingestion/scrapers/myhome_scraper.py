"""MyHome.ie Playwright scraper for single property listings."""
from __future__ import annotations

import json
import re

from bs4 import BeautifulSoup
from playwright.async_api import Browser

from ingestion.scrapers.base_scraper import get_page_html
from ingestion.scrapers.daft_scraper import ListingData, _detect_property_type


def parse_myhome_listing_html(html: str, url: str) -> ListingData | None:
    """Parse a single MyHome.ie property detail page. Returns None if required fields are absent."""
    soup = BeautifulSoup(html, "lxml")

    source_id_match = re.search(r"/(\d+)/?$", url)
    source_id = source_id_match.group(1) if source_id_match else url.split("/")[-1]

    # Address — class-based selector first, fall back to first h1
    addr_el = soup.find(class_=re.compile(r"address", re.I)) or soup.find("h1")
    address = addr_el.get_text(strip=True) if addr_el else ""

    # Price — match any element whose class contains "price"
    price_el = soup.find(class_=re.compile(r"price", re.I))
    price = None
    if price_el:
        price_text = price_el.get_text(strip=True).replace("€", "").replace(",", "").strip()
        try:
            price = int(float(price_text.split()[0]))
        except (ValueError, IndexError):
            pass

    # Guard: both address and price missing means the page is unusable
    if not address and price is None:
        return None

    # Beds / baths — regex over raw HTML (works across most MyHome layouts)
    bed_match = re.search(r"(\d+)\s*[Bb]ed", html)
    bedrooms = int(bed_match.group(1)) if bed_match else None

    bath_match = re.search(r"(\d+)\s*[Bb]ath", html)
    bathrooms = int(bath_match.group(1)) if bath_match else None

    # Floor area
    area_match = re.search(r"(\d+)\s*(?:sq\.?\s*m|sqm|m²)", html, re.IGNORECASE)
    carpet_area_sqm = int(area_match.group(1)) if area_match else None

    # BER — primary: LD+JSON schema.org description contains "(rated C1)" pattern
    ber_raw = None
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            desc = data.get("description", "")
            rated_match = re.search(r"\(rated\s+([A-G]\d?)\)", desc, re.IGNORECASE)
            if rated_match:
                ber_raw = rated_match.group(1).upper()
                break
        except (json.JSONDecodeError, AttributeError):
            pass
    # Fallback: dedicated EnergyRating element (older MyHome markup)
    if not ber_raw:
        rating_el = soup.find(class_=re.compile(r"EnergyRating", re.I))
        if rating_el:
            txt = rating_el.get_text(strip=True)
            m = re.search(r"\b([A-G]\d?)\b", txt)
            if m:
                ber_raw = m.group(1).upper()
    # Fallback: plain-text BER label in the HTML body
    if not ber_raw:
        ber_match = re.search(r"BER[:\s]+([A-G]\d?)", html, re.IGNORECASE)
        ber_raw = ber_match.group(1).upper() if ber_match else None

    # Description
    desc_el = soup.find(class_=re.compile(r"description|PropertyDescription", re.I))
    description = desc_el.get_text(strip=True)[:2000] if desc_el else ""

    # Estate agent
    agent_el = soup.find(class_=re.compile(r"agent|AgentName", re.I))
    estate_agent = agent_el.get_text(strip=True)[:256] if agent_el else None

    return ListingData(
        source_id=source_id,
        url=url,
        title=address,
        address=address,
        price=price,
        bedrooms=bedrooms,
        bathrooms=bathrooms,
        carpet_area_sqm=carpet_area_sqm,
        property_type=_detect_property_type(address + " " + description),
        ber_rating=ber_raw,
        description=description,
        estate_agent=estate_agent,
        source="myhome",
    )


async def parse_myhome_url(url: str, browser: Browser) -> ListingData | None:
    """Convenience wrapper: fetch HTML via Playwright then parse."""
    html = await get_page_html(url, browser)
    if not html:
        return None
    return parse_myhome_listing_html(html, url)
