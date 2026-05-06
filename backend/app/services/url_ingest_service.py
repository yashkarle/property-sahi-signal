"""Synchronous single-URL ingestion: detect portal → scrape → upsert → best-effort embed."""

from __future__ import annotations

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

# Allow importing from the ingestion package (repo root is parent of backend/)
_REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from app.models.property import Property  # noqa: E402

logger = structlog.get_logger()

SUPPORTED_PORTALS = {"daft.ie", "myhome.ie"}


def detect_portal(url: str) -> str | None:
    """Return 'daft.ie' or 'myhome.ie' if supported, else None."""
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

    Raises HTTPException 400/422/502 on actionable failures.
    """
    portal = detect_portal(url)
    if portal is None:
        raise HTTPException(
            status_code=400,
            detail="Unsupported portal. Only daft.ie and myhome.ie are supported.",
        )

    # Deferred imports: playwright and ingestion deps only needed at ingest time
    from ingestion.parsers.property_parser import parse_listing  # noqa: PLC0415
    from ingestion.scrapers.base_scraper import browser_context, get_page_html  # noqa: PLC0415
    from ingestion.scrapers.daft_scraper import parse_daft_listing_html  # noqa: PLC0415
    from ingestion.scrapers.myhome_scraper import parse_myhome_listing_html  # noqa: PLC0415

    async with browser_context() as browser:
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

    prop_dict = parse_listing(listing)
    prop_id = await _upsert_property(db, prop_dict)

    # Best-effort geocoding — needed for pricing model comparables
    await _geocode_if_missing(db, prop_id, prop_dict.get("address", ""))

    # Best-effort: never 500 on embedding failure
    await _enrich_embedding(prop_id, prop_dict)

    result = await db.execute(
        select(Property)
        .where(Property.id == prop_id)
        .options(selectinload(Property.neighbourhood_score))
    )
    prop = result.scalar_one_or_none()
    if prop is None:
        raise HTTPException(status_code=404, detail="Property not found after upsert.")
    return prop


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

    # On conflict: update mutable fields but preserve immutable identity fields
    update_values = {
        k: v for k, v in insert_values.items() if k not in ("id", "source", "source_id", "url")
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


async def _geocode_if_missing(db: AsyncSession, prop_id: uuid.UUID, address: str) -> None:
    """Geocode address and update lat/lng if not already set. Uses Nominatim (free)."""
    if not address:
        return
    try:
        result = await db.execute(select(Property.latitude).where(Property.id == prop_id))
        if result.scalar_one_or_none() is not None:
            return  # already geocoded

        import re as _re  # noqa: PLC0415

        from geopy.adapters import AioHTTPAdapter  # noqa: PLC0415
        from geopy.geocoders import Nominatim  # noqa: PLC0415
        from sqlalchemy import update  # noqa: PLC0415

        # Strip trailing eircode (e.g. "D24 Y161") before passing to Nominatim —
        # the full eircode confuses the geocoder and produces a wrong location.
        clean_address = _re.sub(r",?\s*[A-Z]\d{2}\s+[A-Z0-9]{4}\s*$", "", address).strip()

        # Build progressively broader queries: cleaned full address → suburb → district
        suburb_match = _re.search(
            r",\s*([^,]+(?:Hill|Road|Avenue|Street|Lane|Park|Drive|Way|Court|Grove|Rise|Close|Place|Hall)),",
            clean_address,
        )
        suburb = suburb_match.group(1).strip() if suburb_match else None
        district_match = _re.search(r"\b(D\d{1,2}W?)\b", clean_address.upper())
        district_code = district_match.group(1) if district_match else None
        queries = [
            f"{clean_address}, Dublin, Ireland",
            *([f"{suburb}, Dublin, Ireland"] if suburb else []),
            *([f"Dublin {district_code.lstrip('D')}, Ireland"] if district_code else []),
            "Dublin, Ireland",
        ]

        location = None
        async with Nominatim(
            user_agent="property-sahi-signal",
            adapter_factory=AioHTTPAdapter,
        ) as geolocator:
            for q in queries:
                location = await geolocator.geocode(q, timeout=10)
                if location:
                    break

        if location:
            # Derive Dublin district from eircode in address (e.g. "D24 RX99" → "D24")
            district = None
            eircode_match = _re.search(r"\b(D\d{1,2}W?)\b", address.upper())
            if eircode_match:
                district_map = {
                    "D1": "D1",
                    "D2": "D2",
                    "D4": "D4",
                    "D6": "D6",
                    "D6W": "D6W",
                    "D7": "D7",
                    "D8": "D8",
                    "D9": "D9",
                    "D10": "D10",
                    "D11": "D11",
                    "D12": "D12",
                    "D14": "D14",
                    "D15": "D15",
                    "D16": "D16",
                    "D18": "D18",
                    "D20": "D20",
                    "D22": "D22",
                    "D24": "D24",
                }
                district = district_map.get(eircode_match.group(1))

            await db.execute(
                update(Property)
                .where(Property.id == prop_id)
                .values(
                    latitude=location.latitude,
                    longitude=location.longitude,
                    dublin_district=district,
                )
            )
            await db.commit()
            logger.info(
                "url_ingest_geocoded",
                prop_id=str(prop_id),
                lat=location.latitude,
                lng=location.longitude,
            )
    except Exception as exc:
        logger.warning("url_ingest_geocoding_skipped", prop_id=str(prop_id), error=str(exc))


async def _enrich_embedding(prop_id: uuid.UUID, prop_dict: dict) -> None:
    """Compute Titan embedding + upsert to OpenSearch. Silently skipped on any failure."""
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
