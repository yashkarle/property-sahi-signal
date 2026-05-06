# URL Ingest Endpoint Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `POST /api/v1/ingest/url` — accepts a Daft or MyHome listing URL, scrapes it synchronously, upserts to Postgres, and returns a `PropertyDetail` so buyers can immediately continue through the 6-stage pipeline.

**Architecture:** Service layer calls `get_page_html` (existing Playwright helper) then a portal-specific HTML parser, upserts via SQLAlchemy `pg_insert.on_conflict_do_update` on the `properties.url` unique constraint, and kicks off best-effort Titan embedding. Frontend gets a compact URL import box above the existing search bar that navigates to the property detail page on success.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 (async), Playwright (via ingestion package), BeautifulSoup4, TanStack Query v5, React 18 + TypeScript

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `backend/tests/fixtures/daft_sample.html` | Minimal Daft HTML for parser unit tests |
| Create | `backend/tests/fixtures/myhome_sample.html` | Minimal MyHome HTML for parser unit tests |
| Create | `backend/tests/unit/test_portal_detection.py` | Table-driven tests for `detect_portal()` |
| Create | `backend/tests/unit/test_daft_parser.py` | Regression guard for `parse_daft_listing_html` |
| Create | `backend/tests/unit/test_myhome_parser.py` | Parser tests against myhome fixture |
| Create | `backend/tests/conftest.py` | TestContainers Postgres + async DB session + client fixtures |
| Create | `backend/tests/integration/test_ingest_router.py` | Happy path + 4 error paths with monkeypatched Playwright |
| Modify | `ingestion/scrapers/daft_scraper.py` | `DaftListing→ListingData` (+ `source` field), extract `parse_daft_listing_html`, add `parse_daft_url` wrapper |
| Modify | `ingestion/parsers/property_parser.py` | Use `listing.source` instead of hardcoded `"daft"` |
| Create | `ingestion/scrapers/myhome_scraper.py` | `parse_myhome_listing_html` + `parse_myhome_url` wrapper |
| Create | `backend/app/services/url_ingest_service.py` | `detect_portal`, `ingest_from_url` |
| Create | `backend/app/routers/ingest.py` | `POST /url` route thin HTTP layer |
| Modify | `backend/app/main.py` | Register ingest router at `/api/v1` |
| Modify | `backend/pyproject.toml` | Add `playwright`, `beautifulsoup4`, `lxml` deps + `pythonpath` for pytest |
| Modify | `frontend/src/api/search.ts` | Add `importFromUrl` mutation |
| Modify | `frontend/src/pages/SearchPage.tsx` | URL import input + error display above search bar |

---

## Task 1: Create HTML Test Fixtures

**Files:**
- Create: `backend/tests/fixtures/daft_sample.html`
- Create: `backend/tests/fixtures/myhome_sample.html`

- [ ] **Step 1: Create the fixtures directory and daft fixture**

```bash
mkdir -p backend/tests/fixtures
```

Write `backend/tests/fixtures/daft_sample.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head><title>3 Bed House, Stocking Wood Hall, Rathfarnham, Dublin 16 | Daft.ie</title></head>
<body>
  <h1>3 Bed Semi-Detached House, Stocking Wood Hall, Rathfarnham, Dublin 16</h1>
  <div data-testid="price">€375,000</div>
  <p>3 Bedrooms</p>
  <p>2 Bathrooms</p>
  <p>105 sq. m</p>
  <p>BER: B2</p>
  <div data-testid="description">A well-maintained 3 bedroom semi-detached house. Gas central heating. Chain free. Built in 2015.</div>
  <div class="agent">Sherry FitzGerald</div>
</body>
</html>
```

- [ ] **Step 2: Create the myhome fixture**

Write `backend/tests/fixtures/myhome_sample.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head><title>Stocking Wood Hall, Rathfarnham, Dublin 16 | MyHome.ie</title></head>
<body>
  <h1>Stocking Wood Hall, Rathfarnham, Dublin 16</h1>
  <p class="PropertyPrice__price">€380,000</p>
  <ul>
    <li class="PropertyDetails__bed">3 Beds</li>
    <li class="PropertyDetails__bath">2 Baths</li>
    <li>110 m²</li>
  </ul>
  <span class="EnergyRating__text">B1</span>
  <div class="PropertyDescription__text">Lovely 3 bedroom semi-detached house. Gas central heating. Chain free. Built in 2016.</div>
  <p class="PropertyAgentName__name">DNG Estate Agents</p>
</body>
</html>
```

- [ ] **Step 3: Commit**

```bash
git add backend/tests/fixtures/
git commit -m "test: add HTML fixtures for parser unit tests"
```

---

## Task 2: Write All Failing Unit Tests (TDD)

**Files:**
- Create: `backend/tests/unit/test_portal_detection.py`
- Create: `backend/tests/unit/test_daft_parser.py`
- Create: `backend/tests/unit/test_myhome_parser.py`

- [ ] **Step 1: Write portal detection tests**

Write `backend/tests/unit/test_portal_detection.py`:

```python
import pytest
from app.services.url_ingest_service import detect_portal


@pytest.mark.parametrize("url,expected", [
    ("https://www.daft.ie/for-sale/house/6519399", "daft.ie"),
    ("https://daft.ie/for-sale/apartment/123", "daft.ie"),
    ("https://www.myhome.ie/residential/brochure/house/12345", "myhome.ie"),
    ("https://myhome.ie/residential/brochure/house/12345", "myhome.ie"),
    ("https://www.mulleryogara.ie/property/123", None),
    ("https://www.google.com", None),
    ("not-a-url", None),
    ("", None),
])
def test_detect_portal(url: str, expected: str | None) -> None:
    assert detect_portal(url) == expected
```

- [ ] **Step 2: Write daft parser regression tests**

Write `backend/tests/unit/test_daft_parser.py`:

```python
from pathlib import Path
from ingestion.scrapers.daft_scraper import parse_daft_listing_html

FIXTURE = Path(__file__).parent.parent / "fixtures" / "daft_sample.html"
URL = "https://www.daft.ie/for-sale/house-stocking-wood-hall/6519399"


def test_parse_daft_listing_html_happy_path() -> None:
    listing = parse_daft_listing_html(FIXTURE.read_text(), URL)
    assert listing is not None
    assert listing.price == 375000
    assert listing.bedrooms == 3
    assert listing.bathrooms == 2
    assert listing.carpet_area_sqm == 105
    assert listing.ber_rating == "B2"
    assert listing.source_id == "6519399"
    assert listing.source == "daft"
    assert listing.url == URL


def test_parse_daft_listing_html_returns_none_on_missing_required_fields() -> None:
    result = parse_daft_listing_html("<html><body></body></html>", URL)
    assert result is None
```

- [ ] **Step 3: Write myhome parser tests**

Write `backend/tests/unit/test_myhome_parser.py`:

```python
from pathlib import Path
from ingestion.scrapers.myhome_scraper import parse_myhome_listing_html

FIXTURE = Path(__file__).parent.parent / "fixtures" / "myhome_sample.html"
URL = "https://www.myhome.ie/residential/brochure/stocking-wood-hall/12345"


def test_parse_myhome_listing_html_happy_path() -> None:
    listing = parse_myhome_listing_html(FIXTURE.read_text(), URL)
    assert listing is not None
    assert listing.price == 380000
    assert listing.bedrooms == 3
    assert listing.bathrooms == 2
    assert listing.carpet_area_sqm == 110
    assert listing.ber_rating == "B1"
    assert listing.source_id == "12345"
    assert listing.source == "myhome"
    assert listing.url == URL


def test_parse_myhome_listing_html_returns_none_on_missing_required_fields() -> None:
    result = parse_myhome_listing_html("<html><body></body></html>", URL)
    assert result is None
```

- [ ] **Step 4: Run all unit tests — expect failures/import errors**

```bash
cd backend && pytest tests/unit/ -v 2>&1 | head -40
```

Expected: `ImportError` or `ModuleNotFoundError` on all three — that's correct for TDD.

- [ ] **Step 5: Commit the failing tests**

```bash
git add backend/tests/unit/
git commit -m "test: add failing unit tests for portal detection and parsers (TDD)"
```

---

## Task 3: Refactor `daft_scraper.py` + Update `property_parser.py`

**Files:**
- Modify: `ingestion/scrapers/daft_scraper.py`
- Modify: `ingestion/parsers/property_parser.py`

- [ ] **Step 1: Rename `DaftListing` → `ListingData`, add `source` field, make parse function public**

Replace the entire content of `ingestion/scrapers/daft_scraper.py` with:

```python
"""Daft.ie Playwright scraper for active property listings in Dublin."""
import re
from dataclasses import dataclass, field

from bs4 import BeautifulSoup

from ingestion.scrapers.base_scraper import get_browser, get_page_html

DAFT_SEARCH_URL = (
    "https://www.daft.ie/property-for-sale/dublin"
    "?numBeds_from=2&numBeds_to=4&mnp={min_price}&mxp={max_price}&from={offset}"
)


@dataclass
class ListingData:
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
    source: str = "daft"


# Alias so existing Lambda imports continue to work without modification
DaftListing = ListingData


async def scrape_daft_search(
    min_price: int = 200000,
    max_price: int = 400000,
    max_pages: int = 10,
) -> list[ListingData]:
    browser = await get_browser()
    listings = []
    try:
        for page_num in range(max_pages):
            offset = page_num * 20
            url = DAFT_SEARCH_URL.format(
                min_price=min_price, max_price=max_price, offset=offset
            )
            html = await get_page_html(url, browser)
            if not html:
                break

            page_listings = _parse_search_results(html)
            if not page_listings:
                break

            for listing_url in page_listings:
                detail_html = await get_page_html(listing_url, browser)
                if detail_html:
                    listing = parse_daft_listing_html(detail_html, listing_url)
                    if listing:
                        listings.append(listing)
    finally:
        await browser.close()
    return listings


async def parse_daft_url(url: str, browser) -> ListingData | None:
    """Convenience wrapper: fetch HTML via Playwright then parse. Used by Lambda and single-URL import."""
    html = await get_page_html(url, browser)
    if not html:
        return None
    return parse_daft_listing_html(html, url)


def parse_daft_listing_html(html: str, url: str) -> ListingData | None:
    """Parse a single Daft.ie property detail page. Returns None if required fields are absent."""
    soup = BeautifulSoup(html, "lxml")

    source_id = re.search(r"/(\d+)/?$", url)
    source_id_str = source_id.group(1) if source_id else url.split("/")[-1]

    title_el = soup.find("h1")
    title = title_el.get_text(strip=True) if title_el else ""
    address = title

    price_el = soup.find(attrs={"data-testid": "price"}) or soup.find(class_=re.compile(r"price", re.I))
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

    bedrooms = _extract_number(soup, r"(\d+)\s*[Bb]ed")
    bathrooms = _extract_number(soup, r"(\d+)\s*[Bb]ath")

    area_match = re.search(r"(\d+)\s*(?:sq\.?\s*m|sqm|m²)", html, re.IGNORECASE)
    carpet_area_sqm = int(area_match.group(1)) if area_match else None

    ber_match = re.search(r'BER[:\s]+([A-G]\d?)', html, re.IGNORECASE)
    ber_rating = ber_match.group(1).upper() if ber_match else None

    desc_el = soup.find(attrs={"data-testid": "description"}) or soup.find(class_=re.compile(r"description", re.I))
    description = desc_el.get_text(strip=True)[:2000] if desc_el else ""

    agent_el = soup.find(class_=re.compile(r"agent|estate", re.I))
    estate_agent = agent_el.get_text(strip=True)[:256] if agent_el else None

    return ListingData(
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
        source="daft",
    )


def _parse_search_results(html: str) -> list[str]:
    """Extract property detail URLs from search results page."""
    soup = BeautifulSoup(html, "lxml")
    urls = []
    for a in soup.find_all("a", href=re.compile(r"/for-sale/")):
        href = a.get("href", "")
        if href and href not in urls:
            full_url = f"https://www.daft.ie{href}" if href.startswith("/") else href
            urls.append(full_url)
    return urls[:20]


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
```

- [ ] **Step 2: Update `property_parser.py` to use `listing.source`**

Replace the entire content of `ingestion/parsers/property_parser.py` with:

```python
"""Convert ListingData dataclass → dict ready for Postgres upsert."""
import re
from datetime import datetime, timezone

from ingestion.scrapers.daft_scraper import ListingData

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


def parse_listing(listing: ListingData) -> dict:
    """Convert a scraped ListingData to a Postgres-ready dict."""
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
        "source": listing.source,
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
```

- [ ] **Step 3: Add `pythonpath` to backend pytest config so `import ingestion` resolves when running from `backend/`**

In `backend/pyproject.toml`, replace:
```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```
with:
```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
pythonpath = ["..", "."]
```

- [ ] **Step 4: Run daft parser tests — expect pass**

```bash
cd backend && pytest tests/unit/test_daft_parser.py -v
```

Expected: Both tests PASS.

- [ ] **Step 5: Confirm Lambda path still works (no imports broken)**

```bash
cd backend && python -c "from ingestion.parsers.property_parser import parse_listing; from ingestion.scrapers.daft_scraper import DaftListing; print('OK')"
```

Expected: prints `OK`.

- [ ] **Step 6: Commit**

```bash
git add ingestion/scrapers/daft_scraper.py ingestion/parsers/property_parser.py backend/pyproject.toml
git commit -m "refactor(ingestion): rename DaftListing→ListingData, extract parse_daft_listing_html, use listing.source"
```

---

## Task 4: Create `myhome_scraper.py`

**Files:**
- Create: `ingestion/scrapers/myhome_scraper.py`

- [ ] **Step 1: Write the myhome scraper**

Write `ingestion/scrapers/myhome_scraper.py`:

```python
"""MyHome.ie Playwright scraper for single property listings."""
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

    # BER — try class selector, fall back to text regex
    ber_el = soup.find(class_=re.compile(r"EnergyRating|BerRating|ber", re.I))
    ber_raw = ber_el.get_text(strip=True).upper() if ber_el else None
    if not ber_raw:
        ber_match = re.search(r'BER[:\s]+([A-G]\d?)', html, re.IGNORECASE)
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
```

- [ ] **Step 2: Run myhome parser tests — expect pass**

```bash
cd backend && pytest tests/unit/test_myhome_parser.py -v
```

Expected: Both tests PASS.

- [ ] **Step 3: Run all unit tests — expect only portal detection to fail**

```bash
cd backend && pytest tests/unit/ -v 2>&1 | tail -20
```

Expected: `test_portal_detection.py` FAILS (ImportError — service doesn't exist yet). Daft and myhome tests PASS.

- [ ] **Step 4: Commit**

```bash
git add ingestion/scrapers/myhome_scraper.py
git commit -m "feat(ingestion): add myhome_scraper with parse_myhome_listing_html"
```

---

## Task 5: Add Playwright + BS4 to Backend Dependencies

**Files:**
- Modify: `backend/pyproject.toml`

- [ ] **Step 1: Add dependencies**

In `backend/pyproject.toml`, in the `dependencies` list, add after the existing entries:

```toml
    # Web scraping (for URL ingest endpoint)
    "playwright==1.48.0",
    "beautifulsoup4==4.12.3",
    "lxml==5.3.0",
```

- [ ] **Step 2: Install and verify**

```bash
cd backend && pip install playwright==1.48.0 beautifulsoup4==4.12.3 lxml==5.3.0
playwright install chromium
```

Expected: No errors.

- [ ] **Step 3: Commit**

```bash
git add backend/pyproject.toml
git commit -m "chore(backend): add playwright, beautifulsoup4, lxml for url ingest endpoint"
```

---

## Task 6: Write Failing Integration Test + Conftest

**Files:**
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/integration/test_ingest_router.py`

- [ ] **Step 1: Create conftest with TestContainers + async DB + client fixtures**

Write `backend/tests/conftest.py`:

```python
import os
import sys

import pytest
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from testcontainers.postgres import PostgresContainer

# Allow importing from the ingestion package when tests run from backend/
_REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)


@pytest.fixture(scope="session")
def postgres_dsn() -> str:
    """Start a Postgres container once per session and create all ORM tables."""
    with PostgresContainer("postgres:15-alpine") as pg:
        sync_url = pg.get_connection_url()
        # Import models so Base.metadata is populated
        import app.models  # noqa: F401
        from app.core.database import Base

        engine = create_engine(sync_url)
        Base.metadata.create_all(engine)
        engine.dispose()

        yield sync_url.replace("postgresql://", "postgresql+asyncpg://")


@pytest.fixture
async def db(postgres_dsn: str) -> AsyncSession:
    """Async DB session for a single test; rolled back on completion."""
    engine = create_async_engine(postgres_dsn)
    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session
        await session.rollback()
    await engine.dispose()


@pytest.fixture
async def client(db: AsyncSession):
    """FastAPI test client with DB dependency wired to the test session."""
    from httpx import AsyncClient, ASGITransport
    from app.main import app
    from app.dependencies import get_db

    async def _override_get_db():
        yield db

    app.dependency_overrides[get_db] = _override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
```

- [ ] **Step 2: Write the integration test**

Write `backend/tests/integration/test_ingest_router.py`:

```python
from pathlib import Path

import pytest
from httpx import AsyncClient

DAFT_HTML = (Path(__file__).parent.parent / "fixtures" / "daft_sample.html").read_text()
DAFT_URL = "https://www.daft.ie/for-sale/house-stocking-wood-hall-rathfarnham-dublin-16/6519399"
API_KEY = "change-me-in-production"


class _FakeBrowser:
    async def close(self) -> None: ...


@pytest.fixture(autouse=True)
def _mock_browser(monkeypatch) -> None:
    async def _get_browser():
        return _FakeBrowser()
    monkeypatch.setattr("app.services.url_ingest_service.get_browser", _get_browser)


async def test_ingest_url_happy_path(client: AsyncClient, monkeypatch) -> None:
    async def _mock_html(url, browser):
        return DAFT_HTML
    monkeypatch.setattr("app.services.url_ingest_service.get_page_html", _mock_html)

    resp = await client.post(
        "/api/v1/ingest/url",
        json={"url": DAFT_URL},
        headers={"X-API-Key": API_KEY},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "id" in data
    assert data["price"] == 375000
    assert data["bedrooms"] == 3
    assert data["bathrooms"] == 2


async def test_ingest_same_url_is_idempotent(client: AsyncClient, monkeypatch) -> None:
    async def _mock_html(url, browser):
        return DAFT_HTML
    monkeypatch.setattr("app.services.url_ingest_service.get_page_html", _mock_html)

    resp1 = await client.post(
        "/api/v1/ingest/url", json={"url": DAFT_URL}, headers={"X-API-Key": API_KEY}
    )
    resp2 = await client.post(
        "/api/v1/ingest/url", json={"url": DAFT_URL}, headers={"X-API-Key": API_KEY}
    )
    assert resp1.status_code == 200
    assert resp2.status_code == 200
    assert resp1.json()["id"] == resp2.json()["id"]


async def test_ingest_unsupported_portal(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/ingest/url",
        json={"url": "https://www.mulleryogara.ie/property/123"},
        headers={"X-API-Key": API_KEY},
    )
    assert resp.status_code == 400
    assert "Unsupported portal" in resp.json()["detail"]


async def test_ingest_portal_unreachable(client: AsyncClient, monkeypatch) -> None:
    async def _mock_none(url, browser):
        return None
    monkeypatch.setattr("app.services.url_ingest_service.get_page_html", _mock_none)

    resp = await client.post(
        "/api/v1/ingest/url", json={"url": DAFT_URL}, headers={"X-API-Key": API_KEY}
    )
    assert resp.status_code == 502


async def test_ingest_parse_failure(client: AsyncClient, monkeypatch) -> None:
    async def _mock_empty(url, browser):
        return "<html><body></body></html>"
    monkeypatch.setattr("app.services.url_ingest_service.get_page_html", _mock_empty)

    resp = await client.post(
        "/api/v1/ingest/url", json={"url": DAFT_URL}, headers={"X-API-Key": API_KEY}
    )
    assert resp.status_code == 422
    assert "Could not parse" in resp.json()["detail"]
```

- [ ] **Step 3: Run integration tests — expect 404 (router not registered yet)**

```bash
cd backend && pytest tests/integration/test_ingest_router.py -v 2>&1 | tail -20
```

Expected: Tests that hit the endpoint return 404 or fail with import errors. That's correct TDD state.

- [ ] **Step 4: Commit**

```bash
git add backend/tests/conftest.py backend/tests/integration/test_ingest_router.py
git commit -m "test: add failing integration tests for url ingest router (TDD)"
```

---

## Task 7: Implement `url_ingest_service.py`

**Files:**
- Create: `backend/app/services/url_ingest_service.py`

- [ ] **Step 1: Write the service**

Write `backend/app/services/url_ingest_service.py`:

```python
"""Synchronous single-URL ingestion service: scrape → upsert → best-effort embed."""
import os
import sys
import uuid
from datetime import datetime, timezone
from urllib.parse import urlparse

import structlog
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

# Allow importing from the ingestion package (sibling of backend/ at repo root)
_REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from ingestion.scrapers.base_scraper import get_browser, get_page_html  # noqa: E402
from ingestion.scrapers.daft_scraper import parse_daft_listing_html  # noqa: E402
from ingestion.scrapers.myhome_scraper import parse_myhome_listing_html  # noqa: E402
from ingestion.parsers.property_parser import parse_listing  # noqa: E402

from app.models.property import Property  # noqa: E402

logger = structlog.get_logger()

SUPPORTED_PORTALS = {"daft.ie", "myhome.ie"}


def detect_portal(url: str) -> str | None:
    """Return the canonical portal hostname ('daft.ie' or 'myhome.ie') or None."""
    if not url:
        return None
    try:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return None
        hostname = (parsed.hostname or "").lower()
        if hostname.startswith("www."):
            hostname = hostname[4:]
        return hostname if hostname in SUPPORTED_PORTALS else None
    except Exception:
        return None


async def ingest_from_url(url: str, db: AsyncSession) -> Property:
    """
    Scrape `url`, upsert into Postgres, attempt embedding, return Property ORM row.

    Raises HTTPException 400/422/502 on user-actionable failures.
    """
    portal = detect_portal(url)
    if portal is None:
        raise HTTPException(
            status_code=400,
            detail="Unsupported portal. Only daft.ie and myhome.ie are supported.",
        )

    browser = await get_browser()
    try:
        html = await get_page_html(url, browser)
        if html is None:
            raise HTTPException(status_code=502, detail="Portal unreachable after retries.")

        if portal == "daft.ie":
            listing = parse_daft_listing_html(html, url)
        else:
            listing = parse_myhome_listing_html(html, url)

        if listing is None:
            raise HTTPException(
                status_code=422,
                detail="Could not parse listing. Page may have been removed or structure changed.",
            )
    finally:
        await browser.close()

    prop_dict = parse_listing(listing)
    prop_id = await _upsert_property(db, prop_dict)

    # Best-effort embedding — never 500 on failure
    await _enrich_embedding(prop_id, prop_dict)

    result = await db.execute(
        select(Property)
        .where(Property.id == prop_id)
        .options(selectinload(Property.neighbourhood_score))
    )
    return result.scalar_one()


async def _upsert_property(db: AsyncSession, prop_dict: dict) -> uuid.UUID:
    """Insert or update on url conflict. Returns the actual row UUID."""
    now = datetime.now(timezone.utc)
    new_id = uuid.uuid4()

    last_scraped = (
        datetime.fromisoformat(prop_dict["last_scraped_at"])
        if prop_dict.get("last_scraped_at")
        else now
    )

    insert_values = {
        "id": new_id,
        "source": prop_dict["source"],
        "source_id": prop_dict["source_id"],
        "url": prop_dict["url"],
        "title": prop_dict.get("title"),
        "address": prop_dict.get("address"),
        "price": prop_dict.get("price"),
        "bedrooms": prop_dict.get("bedrooms"),
        "bathrooms": prop_dict.get("bathrooms"),
        "carpet_area_sqm": prop_dict.get("carpet_area_sqm"),
        "property_type": prop_dict.get("property_type"),
        "ber_rating": prop_dict.get("ber_rating"),
        "heating_type": prop_dict.get("heating_type"),
        "year_built": prop_dict.get("year_built"),
        "management_fee_eur": prop_dict.get("management_fee_eur"),
        "is_chain_free": prop_dict.get("is_chain_free"),
        "is_south_facing": prop_dict.get("is_south_facing"),
        "is_htb_eligible": prop_dict.get("is_htb_eligible"),
        "estate_agent": prop_dict.get("estate_agent"),
        "description": prop_dict.get("description"),
        "features_list": prop_dict.get("features_list", []),
        "missing_data_flags": prop_dict.get("missing_data_flags", []),
        "is_active": True,
        "last_scraped_at": last_scraped,
    }

    # Fields to update on conflict (exclude immutable identity fields)
    update_values = {
        k: v for k, v in insert_values.items()
        if k not in ("id", "source", "source_id", "url")
    }
    update_values["updated_at"] = now

    stmt = (
        pg_insert(Property)
        .values(**insert_values)
        .on_conflict_do_update(index_elements=["url"], set_=update_values)
        .returning(Property.id)
    )
    result = await db.execute(stmt)
    await db.commit()
    return result.scalar_one()


async def _enrich_embedding(prop_id: uuid.UUID, prop_dict: dict) -> None:
    """Compute Titan embedding and upsert to OpenSearch. Silently skipped on any failure."""
    try:
        from app.core.embeddings import build_property_embedding_text, embed_text
        from app.core.opensearch import upsert_property_document

        text = build_property_embedding_text(prop_dict)
        embedding = embed_text(text)

        doc = {
            "property_id": str(prop_id),
            "embedding": embedding,
            "text_content": text,
            "price": prop_dict.get("price"),
            "bedrooms": prop_dict.get("bedrooms"),
            "bathrooms": prop_dict.get("bathrooms"),
            "carpet_area_sqm": prop_dict.get("carpet_area_sqm"),
            "dublin_district": prop_dict.get("dublin_district"),
            "property_type": prop_dict.get("property_type"),
            "heating_type": prop_dict.get("heating_type"),
            "is_chain_free": prop_dict.get("is_chain_free", False),
            "is_htb_eligible": prop_dict.get("is_htb_eligible", False),
            "is_south_facing": prop_dict.get("is_south_facing", False),
            "estate_agent": prop_dict.get("estate_agent"),
            "days_on_market": prop_dict.get("days_on_market"),
            "is_active": True,
        }
        await upsert_property_document(str(prop_id), doc)
        logger.info("url_ingest_embedded", prop_id=str(prop_id))
    except Exception as exc:
        logger.warning("url_ingest_embedding_skipped", prop_id=str(prop_id), error=str(exc))
```

- [ ] **Step 2: Run portal detection unit tests — expect pass**

```bash
cd backend && pytest tests/unit/test_portal_detection.py -v
```

Expected: All 8 parametrized cases PASS.

- [ ] **Step 3: Run all unit tests**

```bash
cd backend && pytest tests/unit/ -v
```

Expected: All unit tests PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/url_ingest_service.py
git commit -m "feat(backend): implement url_ingest_service with detect_portal and upsert logic"
```

---

## Task 8: Create Ingest Router + Register in `main.py`

**Files:**
- Create: `backend/app/routers/ingest.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Write the ingest router**

Write `backend/app/routers/ingest.py`:

```python
from fastapi import APIRouter
from pydantic import BaseModel

from app.dependencies import AuthDep, DbSession
from app.schemas.property import PropertyDetail
from app.services.url_ingest_service import ingest_from_url

router = APIRouter(prefix="/ingest", tags=["ingest"])


class IngestUrlRequest(BaseModel):
    url: str


@router.post("/url", response_model=PropertyDetail)
async def ingest_property_url(
    request: IngestUrlRequest, db: DbSession, _: AuthDep
) -> PropertyDetail:
    prop = await ingest_from_url(request.url, db)
    return PropertyDetail.model_validate(prop)
```

- [ ] **Step 2: Register the router in `main.py`**

In `backend/app/main.py`, change the import line:
```python
from app.routers import admin, bidding, chat, financing, pricing, professionals, search, viewing
```
to:
```python
from app.routers import admin, bidding, chat, financing, ingest, pricing, professionals, search, viewing
```

And add after the existing `app.include_router` calls:
```python
app.include_router(ingest.router, prefix=PREFIX)
```

- [ ] **Step 3: Run integration tests — expect all pass**

```bash
cd backend && pytest tests/integration/test_ingest_router.py -v
```

Expected: All 5 tests PASS.

- [ ] **Step 4: Run the full test suite**

```bash
cd backend && pytest -v
```

Expected: All tests PASS. `make lint` should also pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/ingest.py backend/app/main.py
git commit -m "feat(backend): add POST /api/v1/ingest/url endpoint and register router"
```

---

## Task 9: Frontend — Add `importFromUrl` API Client

**Files:**
- Modify: `frontend/src/api/search.ts`

- [ ] **Step 1: Add the `importFromUrl` mutation**

In `frontend/src/api/search.ts`, append after the last export:

```typescript
export const useImportFromUrl = () =>
  useMutation<PropertyDetail, { response: { data: { detail: string } } }, { url: string }>({
    mutationFn: (req) => apiClient.post('/ingest/url', req).then((r) => r.data),
  })
```

The full file should be:

```typescript
import { useQuery, useMutation } from '@tanstack/react-query'
import { apiClient } from './client'
import type { SearchRequest, SearchResponse, PropertyDetail, CompareResponse } from '../types/property'

export const useSearchProperties = (request: SearchRequest | null) =>
  useMutation<SearchResponse, Error, SearchRequest>({
    mutationFn: (req) => apiClient.post('/search/semantic', req).then((r) => r.data),
  })

export const useProperty = (id: string | undefined) =>
  useQuery<PropertyDetail>({
    queryKey: ['property', id],
    queryFn: () => apiClient.get(`/search/properties/${id}`).then((r) => r.data),
    enabled: !!id,
  })

export const useNeighbourhoodScore = (id: string | undefined) =>
  useQuery({
    queryKey: ['neighbourhood', id],
    queryFn: () => apiClient.get(`/search/properties/${id}/neighbourhood`).then((r) => r.data),
    enabled: !!id,
  })

export const useCompareProperties = () =>
  useMutation<CompareResponse, Error, { property_ids: string[] }>({
    mutationFn: (req) => apiClient.post('/search/properties/compare', req).then((r) => r.data),
  })

export const useImportFromUrl = () =>
  useMutation<PropertyDetail, { response: { data: { detail: string } } }, { url: string }>({
    mutationFn: (req) => apiClient.post('/ingest/url', req).then((r) => r.data),
  })
```

- [ ] **Step 2: Type-check**

```bash
cd frontend && npm run build 2>&1 | tail -20
```

Expected: No TypeScript errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/search.ts
git commit -m "feat(frontend): add useImportFromUrl mutation for POST /api/v1/ingest/url"
```

---

## Task 10: Frontend — Add URL Import UI to `SearchPage.tsx`

**Files:**
- Modify: `frontend/src/pages/SearchPage.tsx`

- [ ] **Step 1: Add the URL import component to SearchPage**

Replace the entire content of `frontend/src/pages/SearchPage.tsx` with:

```tsx
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import type { PropertySummary, SearchFilters } from '../types/property'
import { useSearchProperties, useImportFromUrl } from '../api/search'
import { useComparisonStore } from '../store/comparisonStore'
import { useSessionStore } from '../store/sessionStore'

const DUBLIN_DISTRICTS = ['D1','D2','D3','D4','D6','D6W','D7','D8','D9','D10','D11','D12','D14','D15','D16','D18','D20','D22','D24']
const PROPERTY_TYPES = ['apartment','duplex','house','own_door_apartment']
const BER_RATINGS = ['A1','A2','A3','B1','B2','B3','C1','C2','D1','E1','F','G']

function formatPrice(p: number | undefined) {
  return p ? `€${p.toLocaleString('en-IE')}` : '—'
}

function PropertyCard({ prop }: { prop: PropertySummary }) {
  const { addProperty, removeProperty, selectedProperties } = useComparisonStore()
  const { setActiveProperty } = useSessionStore()
  const navigate = useNavigate()
  const isSelected = selectedProperties.some((p) => p.id === prop.id)

  const warnings: string[] = []
  if (prop.heating_type === 'electric_storage') warnings.push('⚠️ Electric storage heating')
  if ((prop.missing_data_flags || []).includes('carpet_area_sqm')) warnings.push('❗ Missing floor area')
  if (prop.bathrooms === 1) warnings.push('⚠️ Only 1 bathroom')

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4 hover:shadow-md transition-shadow">
      <div className="flex justify-between items-start mb-2">
        <div>
          <h3 className="font-semibold text-gray-900 text-sm leading-tight">
            {prop.address || prop.title || 'Unknown address'}
          </h3>
          <p className="text-xs text-gray-500 mt-0.5">{prop.dublin_district} · {prop.estate_agent}</p>
        </div>
        <span className="text-lg font-bold text-green-700">{formatPrice(prop.price)}</span>
      </div>

      <div className="flex gap-3 text-xs text-gray-600 mb-2">
        <span>{prop.bedrooms}🛏</span>
        <span>{prop.bathrooms}🚿</span>
        {prop.carpet_area_sqm && <span>{prop.carpet_area_sqm}m²</span>}
        {prop.ber_rating && <span className="bg-green-100 text-green-800 px-1.5 rounded">BER {prop.ber_rating}</span>}
        {prop.is_chain_free && <span className="bg-blue-100 text-blue-800 px-1.5 rounded">Chain-free</span>}
      </div>

      {warnings.length > 0 && (
        <div className="mb-2">
          {warnings.map((w) => (
            <p key={w} className="text-xs text-amber-600">{w}</p>
          ))}
        </div>
      )}

      <div className="flex gap-2 mt-3">
        <button
          onClick={() => { setActiveProperty(prop.id); navigate(`/property/${prop.id}`) }}
          className="flex-1 text-xs py-1.5 rounded-lg bg-gray-900 text-white hover:bg-gray-700"
        >
          View Details
        </button>
        <button
          onClick={() => isSelected ? removeProperty(prop.id) : addProperty(prop)}
          className={`text-xs px-3 py-1.5 rounded-lg border transition-colors ${
            isSelected ? 'bg-blue-600 text-white border-blue-600' : 'border-gray-300 text-gray-600 hover:border-blue-400'
          }`}
        >
          {isSelected ? '✓ Compare' : '+ Compare'}
        </button>
      </div>
    </div>
  )
}

function UrlImportBar() {
  const [importUrl, setImportUrl] = useState('')
  const [importError, setImportError] = useState<string | null>(null)
  const navigate = useNavigate()
  const { setActiveProperty } = useSessionStore()
  const { mutate: importProperty, isPending: isImporting } = useImportFromUrl()

  const handleImport = () => {
    const trimmed = importUrl.trim()
    if (!trimmed) return
    setImportError(null)
    importProperty(
      { url: trimmed },
      {
        onSuccess: (prop) => {
          setActiveProperty(prop.id)
          navigate(`/property/${prop.id}`)
        },
        onError: (err) => {
          const detail = err?.response?.data?.detail ?? 'Import failed. Check the URL and try again.'
          setImportError(detail)
        },
      }
    )
  }

  return (
    <div className="mb-6 p-4 bg-gray-50 rounded-xl border border-gray-200">
      <p className="text-xs font-medium text-gray-600 mb-2">
        Import a listing directly — paste a Daft or MyHome URL
      </p>
      <div className="flex gap-2">
        <input
          type="url"
          value={importUrl}
          onChange={(e) => setImportUrl(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleImport()}
          placeholder="https://www.daft.ie/for-sale/..."
          className="flex-1 px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <button
          onClick={handleImport}
          disabled={isImporting || !importUrl.trim()}
          className="px-4 py-2 rounded-lg bg-blue-700 text-white text-sm font-medium hover:bg-blue-600 disabled:opacity-50"
        >
          {isImporting ? 'Importing…' : 'Import'}
        </button>
      </div>
      {importError && (
        <p className="mt-2 text-xs text-red-600">{importError}</p>
      )}
    </div>
  )
}

export default function SearchPage() {
  const [query, setQuery] = useState('')
  const [filters, setFilters] = useState<SearchFilters>({
    price_max: 375000,
    bedrooms_min: 2,
    bathrooms_min: 2,
    carpet_area_sqm_min: 70,
  })
  const { mutate: search, data, isPending } = useSearchProperties(null)

  const handleSearch = () => {
    if (!query.trim()) return
    search({ query, filters, limit: 20 })
  }

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900 mb-1">Property Search</h1>
        <p className="text-sm text-gray-500">Semantic search across Dublin listings — describe what you want</p>
      </div>

      {/* URL import bar */}
      <UrlImportBar />

      {/* Search bar */}
      <div className="flex gap-3 mb-4">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
          placeholder='e.g. "turnkey 2-bed apartment near Luas in D12 with gas heating"'
          className="flex-1 px-4 py-2.5 rounded-xl border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
        />
        <button
          onClick={handleSearch}
          disabled={isPending}
          className="px-6 py-2.5 rounded-xl bg-green-700 text-white text-sm font-medium hover:bg-green-600 disabled:opacity-50"
        >
          {isPending ? 'Searching…' : 'Search'}
        </button>
      </div>

      {/* Quick filters */}
      <div className="flex flex-wrap gap-2 mb-6">
        <select
          className="text-xs px-3 py-1.5 rounded-lg border border-gray-300 bg-white"
          onChange={(e) => setFilters((f) => ({ ...f, price_max: Number(e.target.value) }))}
          defaultValue="375000"
        >
          <option value="325000">Max €325k</option>
          <option value="350000">Max €350k</option>
          <option value="375000">Max €375k</option>
          <option value="400000">Max €400k</option>
        </select>
        <select
          className="text-xs px-3 py-1.5 rounded-lg border border-gray-300 bg-white"
          onChange={(e) => setFilters((f) => ({ ...f, carpet_area_sqm_min: Number(e.target.value) }))}
          defaultValue="70"
        >
          <option value="60">≥60m²</option>
          <option value="70">≥70m² (min)</option>
          <option value="80">≥80m²</option>
        </select>
      </div>

      {/* Results */}
      {data && (
        <div>
          <p className="text-xs text-gray-500 mb-3">
            {data.total} results · {data.query_time_ms}ms
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {data.results.map((prop: PropertySummary) => (
              <PropertyCard key={prop.id} prop={prop} />
            ))}
          </div>
        </div>
      )}

      {!data && !isPending && (
        <div className="text-center py-20 text-gray-400">
          <p className="text-4xl mb-4">🏠</p>
          <p className="text-sm">Describe your ideal property above to get started</p>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Type-check and lint**

```bash
cd frontend && npm run build 2>&1 | tail -20
cd frontend && npm run lint 2>&1 | tail -20
```

Expected: No errors.

- [ ] **Step 3: Verify the UI manually (start both servers)**

```bash
# Terminal 1
cd backend && uvicorn app.main:app --reload --port 8000

# Terminal 2
cd frontend && npm run dev
```

Open `http://localhost:5173`. Verify:
1. The blue "Import a listing" section appears above the green search bar.
2. Entering `https://www.mulleryogara.ie/property/123` and pressing Import shows the red error "Unsupported portal. Only daft.ie and myhome.ie are supported."
3. Entering an invalid URL (no scheme) shows an appropriate error.
4. (If backend is running with DB) Entering a real Daft URL navigates to the property detail page.

- [ ] **Step 4: Run full backend test suite one final time**

```bash
cd backend && pytest -v && make lint
```

Expected: All tests PASS, lint clean.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/SearchPage.tsx frontend/src/api/search.ts
git commit -m "feat(frontend): add URL import bar to SearchPage — navigates to property detail on success"
```

---

## Self-Review: Spec Coverage Check

| Spec requirement | Covered by task |
|------------------|-----------------|
| `POST /api/v1/ingest/url` endpoint | Task 8 |
| Support daft.ie + myhome.ie only, 400 otherwise | Task 7 (`detect_portal`) |
| 400 on invalid URL format | Task 7 (`detect_portal` returns None on parse failure) |
| Reuse `get_page_html` | Task 7 (imported from base_scraper) |
| Daft parser refactored to `parse_daft_listing_html` | Task 3 |
| New `myhome_scraper.py` with `parse_myhome_listing_html` | Task 4 |
| Reuse `property_parser.parse_listing` | Task 7 (called in service) |
| MyHome rows get `source="myhome"` | Task 3 (listing.source) + Task 4 (myhome returns `source="myhome"`) |
| SQLAlchemy upsert via ON CONFLICT (url) | Task 7 (`_upsert_property`) |
| 502 when `get_page_html` returns None | Task 7 + 8 |
| 422 when parser returns None | Task 7 + 8 |
| Best-effort embedding (200 on embed failure) | Task 7 (`_enrich_embedding` wraps in try/except) |
| `selectinload(neighbourhood_score)` for `PropertyDetail` | Task 7 (before `model_validate`) |
| Idempotent — same URL → same property_id | Task 7 (`pg_insert.on_conflict_do_update`) |
| `DaftListing = ListingData` alias (no Lambda breakage) | Task 3 |
| Unit tests: portal detection (table-driven) | Task 2 |
| Unit tests: daft parser against fixture | Task 2 |
| Unit tests: myhome parser against fixture | Task 2 |
| Integration test: happy path + idempotency | Task 6 |
| Integration test: 3 error paths | Task 6 |
| Frontend URL import input above search bar | Task 10 |
| Navigate to `/property/:id` on success | Task 10 |
| Inline error showing server's `detail` | Task 10 |
| `make lint` + `make test` green | Verified in Task 8 + Task 10 |
| Lambda path unbroken | Task 3 (alias + `pythonpath` fix) |

All requirements covered. No gaps found.
