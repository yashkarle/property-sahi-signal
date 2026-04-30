"""Daft.ie Playwright scraper for active property listings in Dublin.

NOTE: Daft.ie is behind Cloudflare Bot Management which blocks headless
Playwright regardless of stealth patches as of 2024+. When run locally
the scraper will return 0 listings ("Just a moment..." challenge page).

For local dev, use `make seed-properties` to populate the database with
realistic sample listings. The Lambda runs in AWS with a residential IP
which is typically not challenged by Cloudflare.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import structlog
from bs4 import BeautifulSoup

from ingestion.scrapers.base_scraper import get_browser, get_page_html

logger = structlog.get_logger()

DAFT_SEARCH_URL = (
    "https://www.daft.ie/property-for-sale/dublin"
    "?numBeds_from=2&numBeds_to=4&mnp={min_price}&mxp={max_price}&from={offset}"
)


@dataclass
class DaftListing:
    source_id: str
    url: str
    title: str
    address: str
    price: int | None
    bedrooms: int | None
    bathrooms: int | None
    carpet_area_sqm: int | None
    property_type: str | None
    ber_rating: str | None
    description: str
    estate_agent: str | None
    features: list[str] = field(default_factory=list)
    raw_html: str = ""


async def scrape_daft_search(
    min_price: int = 200000,
    max_price: int = 400000,
    max_pages: int = 10,
) -> list[DaftListing]:
    browser = await get_browser()
    listings = []
    try:
        for page_num in range(max_pages):
            offset = page_num * 20
            url = DAFT_SEARCH_URL.format(
                min_price=min_price, max_price=max_price, offset=offset
            )
            logger.info("daft_fetching_page", page=page_num + 1, url=url)
            html = await get_page_html(url, browser)
            if not html:
                logger.warning("daft_page_empty", page=page_num + 1)
                break

            page_listings = _parse_search_results(html)
            if not page_listings:
                logger.info("daft_no_more_listings", page=page_num + 1)
                break

            for listing_url in page_listings:
                detail_html = await get_page_html(listing_url, browser)
                if detail_html:
                    listing = _parse_detail_page(detail_html, listing_url)
                    if listing:
                        listings.append(listing)
    finally:
        await browser.close()
    return listings


def _parse_search_results(html: str) -> list[str]:
    """Extract property detail URLs from search results page."""
    soup = BeautifulSoup(html, "lxml")
    urls = []

    # Daft.ie listing URLs follow /for-sale/<slug>/<id> pattern
    # Try both /for-sale/ and /property-for-sale/ paths
    for a in soup.find_all("a", href=re.compile(r"/(for-sale|property-for-sale)/.+/\d+")):
        href = a.get("href", "")
        if not href:
            continue
        full_url = f"https://www.daft.ie{href}" if href.startswith("/") else href
        # Strip query strings
        full_url = full_url.split("?")[0]
        if full_url not in urls:
            urls.append(full_url)

    logger.info("daft_search_page_parsed", found=len(urls), html_len=len(html))
    if not urls:
        # Dump a snippet to help debug selector mismatches
        all_hrefs = [a.get("href", "") for a in soup.find_all("a", href=True)]
        sale_hrefs = [h for h in all_hrefs if "sale" in h.lower()][:10]
        logger.debug("daft_no_listings_found", sample_hrefs=sale_hrefs, title=soup.title.string if soup.title else "")

    return urls[:20]


def _parse_detail_page(html: str, url: str) -> DaftListing | None:
    """Parse a single Daft.ie property detail page."""
    soup = BeautifulSoup(html, "lxml")

    # Extract source_id from URL
    source_id = re.search(r"/(\d+)/?$", url)
    source_id_str = source_id.group(1) if source_id else url.split("/")[-1]

    # Title
    title_el = soup.find("h1")
    title = title_el.get_text(strip=True) if title_el else ""

    # Address — typically in a span or h1 sub-element
    address = title

    # Price
    price_el = soup.find(attrs={"data-testid": "price"}) or soup.find(class_=re.compile(r"price", re.I))
    price = None
    if price_el:
        price_text = price_el.get_text(strip=True).replace("€", "").replace(",", "").strip()
        try:
            price = int(float(price_text.split()[0]))
        except (ValueError, IndexError):
            pass

    # Beds / baths
    bedrooms = _extract_number(soup, r"(\d+)\s*[Bb]ed")
    bathrooms = _extract_number(soup, r"(\d+)\s*[Bb]ath")

    # Floor area
    area_match = re.search(r"(\d+)\s*(?:sq\.?\s*m|sqm|m²)", html, re.IGNORECASE)
    carpet_area_sqm = int(area_match.group(1)) if area_match else None

    # BER
    ber_match = re.search(r'BER[:\s]+([A-G]\d?)', html, re.IGNORECASE)
    ber_rating = ber_match.group(1).upper() if ber_match else None

    # Description
    desc_el = soup.find(attrs={"data-testid": "description"}) or soup.find(class_=re.compile(r"description", re.I))
    description = desc_el.get_text(strip=True)[:2000] if desc_el else ""

    # Agent
    agent_el = soup.find(class_=re.compile(r"agent|estate", re.I))
    estate_agent = agent_el.get_text(strip=True)[:256] if agent_el else None

    return DaftListing(
        source_id=source_id_str,
        url=url,
        title=title,
        address=address,
        price=price,
        bedrooms=bedrooms,
        bathrooms=bathrooms,
        carpet_area_sqm=carpet_area_sqm,
        property_type=_detect_property_type(title + description),
        ber_rating=ber_rating,
        description=description,
        estate_agent=estate_agent,
        raw_html=html[:5000],
    )


def _extract_number(soup: BeautifulSoup, pattern: str) -> int | None:
    text = soup.get_text()
    match = re.search(pattern, text)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            pass
    return None


def _detect_property_type(text: str) -> str | None:
    text_lower = text.lower()
    if "own door" in text_lower or "own-door" in text_lower:
        return "own_door_apartment"
    if "duplex" in text_lower:
        return "duplex"
    if "apartment" in text_lower or "flat" in text_lower:
        return "apartment"
    if "house" in text_lower or "semi-detached" in text_lower or "detached" in text_lower:
        return "house"
    return None
