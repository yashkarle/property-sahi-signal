"""AWS Lambda entry point for scheduled property ingestion.

Triggered by EventBridge every 6 hours.
Scrapes Daft.ie + downloads PPR CSV and ingests into Postgres + OpenSearch.

Can also run locally:
    DATABASE_URL=postgresql://... python ingestion/lambda_handler.py
"""
import asyncio
import json
import os
import sys
import uuid
from datetime import date, datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import asyncpg
import structlog

logger = structlog.get_logger()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://property_user:property_pass@localhost:5432/property_sahi",
).replace("postgresql+asyncpg://", "postgresql://")

OPENSEARCH_ENDPOINT = os.getenv("OPENSEARCH_ENDPOINT", "http://localhost:4566")
OPENSEARCH_INDEX = os.getenv("OPENSEARCH_INDEX", "properties-v1")
USE_LOCALSTACK = os.getenv("USE_LOCALSTACK", "true").lower() == "true"


async def run_ingestion(event: dict = {}, context=None) -> dict:
    logger.info("ingestion_start")
    results: dict = {"daft": 0, "ppr": 0, "errors": []}

    pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=5)
    try:
        await _ingest_ppr(pool, results)
        await _ingest_daft(pool, results)
    finally:
        await pool.close()

    logger.info("ingestion_complete", **results)
    return results


async def _ingest_ppr(pool: asyncpg.Pool, results: dict) -> None:
    try:
        from ingestion.scrapers.ppr_scraper import download_ppr_csv, filter_dublin_records
        from ingestion.parsers.ppr_parser import parse_ppr_record

        year = date.today().year
        ppr_records = await download_ppr_csv(year)
        dublin_records = filter_dublin_records(ppr_records)
        logger.info("ppr_downloaded", total=len(ppr_records), dublin=len(dublin_records))

        source_file = f"PPR-{year}"
        rows = [parse_ppr_record(r, source_file) for r in dublin_records]
        inserted = await _upsert_ppr_records(pool, rows)
        results["ppr"] = inserted
        logger.info("ppr_upserted", count=inserted)
    except Exception as e:
        logger.error("ppr_failed", error=str(e))
        results["errors"].append(f"PPR: {e}")


async def _ingest_daft(pool: asyncpg.Pool, results: dict) -> None:
    try:
        from ingestion.scrapers.daft_scraper import scrape_daft_search
        from ingestion.parsers.property_parser import parse_listing
        from ingestion.enrichment.geocoder import geocode_address

        listings = await scrape_daft_search(
            min_price=int(os.getenv("MIN_PRICE", "200000")),
            max_price=int(os.getenv("MAX_PRICE", "400000")),
            max_pages=int(os.getenv("MAX_PAGES", "5")),
        )
        logger.info("daft_scraped", count=len(listings))

        inserted = 0
        for listing in listings:
            try:
                prop_dict = parse_listing(listing)

                # Geocode if no lat/lng
                if not prop_dict.get("latitude") and prop_dict.get("address"):
                    geo = await geocode_address(prop_dict["address"])
                    prop_dict.update(geo)

                prop_id = await _upsert_property(pool, prop_dict)
                if prop_id:
                    await _enrich_with_embedding(pool, prop_id, prop_dict)
                    inserted += 1
            except Exception as e:
                logger.warning("listing_failed", url=listing.url, error=str(e))

        results["daft"] = inserted
        logger.info("daft_upserted", count=inserted)
    except Exception as e:
        logger.error("daft_failed", error=str(e))
        results["errors"].append(f"Daft: {e}")


async def _upsert_property(pool: asyncpg.Pool, prop: dict) -> str | None:
    """Upsert a property record. Returns the property UUID."""
    prop_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    async with pool.acquire() as conn:
        existing = await conn.fetchval(
            "SELECT id::text FROM properties WHERE url = $1", prop["url"]
        )
        if existing:
            # Update existing record
            await conn.execute(
                """UPDATE properties SET
                    price = $2, bedrooms = $3, bathrooms = $4,
                    carpet_area_sqm = $5, ber_rating = $6, heating_type = $7::heating_type_enum,
                    is_chain_free = $8, is_south_facing = $9, estate_agent = $10,
                    description = $11, missing_data_flags = $12::jsonb,
                    last_scraped_at = $13, updated_at = $13, is_active = true
                WHERE url = $1""",
                prop["url"], prop.get("price"), prop.get("bedrooms"), prop.get("bathrooms"),
                prop.get("carpet_area_sqm"), prop.get("ber_rating"), prop.get("heating_type"),
                prop.get("is_chain_free"), prop.get("is_south_facing"), prop.get("estate_agent"),
                prop.get("description"), json.dumps(prop.get("missing_data_flags", [])),
                now,
            )
            return existing
        else:
            await conn.execute(
                """INSERT INTO properties (
                    id, source, source_id, url, title, address,
                    latitude, longitude, dublin_district, eircode,
                    price, bedrooms, bathrooms, carpet_area_sqm,
                    property_type, ber_rating, heating_type, year_built,
                    management_fee_eur, is_chain_free, is_south_facing,
                    is_htb_eligible, estate_agent, description,
                    features_list, missing_data_flags, is_active,
                    last_scraped_at, created_at, updated_at
                ) VALUES (
                    $1::uuid, $2::source_enum, $3, $4, $5, $6,
                    $7, $8, $9, $10,
                    $11, $12, $13, $14,
                    $15::property_type_enum, $16, $17::heating_type_enum, $18,
                    $19, $20, $21,
                    $22, $23, $24,
                    $25::jsonb, $26::jsonb, $27,
                    $28, $28, $28
                )""",
                prop_id, prop["source"], prop["source_id"], prop["url"],
                prop.get("title"), prop.get("address"),
                prop.get("latitude"), prop.get("longitude"),
                prop.get("dublin_district"), prop.get("eircode"),
                prop.get("price"), prop.get("bedrooms"), prop.get("bathrooms"),
                prop.get("carpet_area_sqm"),
                prop.get("property_type"), prop.get("ber_rating"),
                prop.get("heating_type"), prop.get("year_built"),
                prop.get("management_fee_eur"), prop.get("is_chain_free"),
                prop.get("is_south_facing"),
                prop.get("is_htb_eligible"), prop.get("estate_agent"),
                prop.get("description"),
                json.dumps(prop.get("features_list", [])),
                json.dumps(prop.get("missing_data_flags", [])),
                prop.get("is_active", True),
                now,
            )
            return prop_id


async def _upsert_ppr_records(pool: asyncpg.Pool, rows: list[dict]) -> int:
    inserted = 0
    async with pool.acquire() as conn:
        for row in rows:
            try:
                result = await conn.execute(
                    """INSERT INTO ppr_sales (
                        id, address, eircode, county, date_of_sale, price_eur,
                        not_full_market_price, vat_exclusive, property_description,
                        dublin_district, source_file, scraped_at
                    ) VALUES (
                        $1::uuid, $2, $3, $4, $5::date, $6,
                        $7, $8, $9, $10, $11, NOW()
                    ) ON CONFLICT (address, date_of_sale, price_eur) DO NOTHING""",
                    str(uuid.uuid4()),
                    row["address"], row["eircode"], row["county"],
                    row["date_of_sale"], row["price_eur"],
                    row["not_full_market_price"], row["vat_exclusive"],
                    row["property_description"],
                    row["dublin_district"], row["source_file"],
                )
                if result != "INSERT 0 0":
                    inserted += 1
            except Exception as e:
                logger.debug("ppr_row_skip", error=str(e))
    return inserted


async def _enrich_with_embedding(pool: asyncpg.Pool, prop_id: str, prop: dict) -> None:
    """Compute Titan embedding and upsert to OpenSearch."""
    try:
        import boto3
        from ingestion.enrichment.embedding_enricher import (
            get_bedrock_client,
            embed_property_text,
            build_opensearch_document,
        )

        text = _build_embedding_text(prop)
        bedrock = get_bedrock_client(USE_LOCALSTACK, OPENSEARCH_ENDPOINT)
        embedding = embed_property_text(text, bedrock)

        doc = build_opensearch_document(prop_id, text, embedding, {
            "price": prop.get("price"),
            "bedrooms": prop.get("bedrooms"),
            "bathrooms": prop.get("bathrooms"),
            "carpet_area_sqm": prop.get("carpet_area_sqm"),
            "dublin_district": prop.get("dublin_district"),
            "property_type": prop.get("property_type"),
            "heating_type": prop.get("heating_type"),
            "is_chain_free": prop.get("is_chain_free", False),
            "is_htb_eligible": prop.get("is_htb_eligible", False),
            "is_south_facing": prop.get("is_south_facing", False),
            "estate_agent": prop.get("estate_agent"),
            "days_on_market": prop.get("days_on_market"),
            "is_active": True,
        })

        await _push_to_opensearch(prop_id, doc)

        # Record embedding_id on property
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE properties SET embedding_id = $2 WHERE id = $1::uuid",
                prop_id, prop_id,
            )
    except Exception as e:
        logger.warning("embedding_failed", prop_id=prop_id, error=str(e))


async def _push_to_opensearch(doc_id: str, document: dict) -> None:
    import httpx
    url = f"{OPENSEARCH_ENDPOINT}/{OPENSEARCH_INDEX}/_doc/{doc_id}"
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.put(url, json=document, auth=("admin", "admin"))
        resp.raise_for_status()


def _build_embedding_text(prop: dict) -> str:
    parts = [
        prop.get("address", ""),
        prop.get("dublin_district", ""),
        f"{prop.get('property_type', '')} with {prop.get('bedrooms', '?')} bedrooms",
    ]
    if prop.get("carpet_area_sqm"):
        parts.append(f"{prop['carpet_area_sqm']}sqm carpet area")
    if prop.get("ber_rating"):
        parts.append(f"BER {prop['ber_rating']}")
    if prop.get("heating_type"):
        parts.append(f"{prop['heating_type']} heating")
    if prop.get("description"):
        parts.append(prop["description"][:500])
    return ". ".join(p for p in parts if p)


def handler(event: dict, context) -> dict:
    return asyncio.run(run_ingestion(event, context))


if __name__ == "__main__":
    result = asyncio.run(run_ingestion())
    print(json.dumps(result, indent=2))
