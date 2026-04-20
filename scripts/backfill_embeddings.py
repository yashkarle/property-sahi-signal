"""Backfill embeddings for all properties that lack an embedding_id.

Fetches each property from Postgres, computes Titan v2 embedding via Bedrock,
and upserts the document to OpenSearch.

Usage:
    DATABASE_URL=postgresql://property_user:property_pass@localhost:5432/property_sahi \
    AWS_DEFAULT_REGION=eu-west-1 \
    OPENSEARCH_ENDPOINT=http://localhost:4566 \
        python scripts/backfill_embeddings.py
"""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import asyncpg
import httpx

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://property_user:property_pass@localhost:5432/property_sahi",
).replace("postgresql+asyncpg://", "postgresql://")

OPENSEARCH_ENDPOINT = os.getenv("OPENSEARCH_ENDPOINT", "http://localhost:4566")
OPENSEARCH_INDEX = os.getenv("OPENSEARCH_INDEX", "properties-v1")
USE_LOCALSTACK = os.getenv("USE_LOCALSTACK", "true").lower() == "true"
BATCH_SIZE = 10


def _build_text(row: dict) -> str:
    parts = [
        row.get("address") or "",
        row.get("dublin_district") or "",
        f"{row.get('property_type') or ''} with {row.get('bedrooms') or '?'} bedrooms",
    ]
    if row.get("carpet_area_sqm"):
        parts.append(f"{row['carpet_area_sqm']}sqm carpet area")
    if row.get("ber_rating"):
        parts.append(f"BER {row['ber_rating']}")
    if row.get("heating_type"):
        parts.append(f"{row['heating_type']} heating")
    if row.get("description"):
        parts.append(str(row["description"])[:500])
    return ". ".join(p for p in parts if p)


def _embed(text: str, bedrock_client) -> list[float]:
    resp = bedrock_client.invoke_model(
        modelId="amazon.titan-embed-text-v2:0",
        body=json.dumps({"inputText": text}),
        contentType="application/json",
    )
    return json.loads(resp["body"].read())["embedding"]


async def _upsert_os(prop_id: str, doc: dict) -> None:
    url = f"{OPENSEARCH_ENDPOINT}/{OPENSEARCH_INDEX}/_doc/{prop_id}"
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.put(url, json=doc, auth=("admin", "admin"))
        r.raise_for_status()


async def backfill():
    import boto3

    bedrock_kwargs: dict = {
        "service_name": "bedrock-runtime",
        "region_name": os.getenv("AWS_DEFAULT_REGION", "eu-west-1"),
        "aws_access_key_id": os.getenv("AWS_ACCESS_KEY_ID", "test"),
        "aws_secret_access_key": os.getenv("AWS_SECRET_ACCESS_KEY", "test"),
    }
    if USE_LOCALSTACK:
        bedrock_kwargs["endpoint_url"] = OPENSEARCH_ENDPOINT
    bedrock = boto3.client(**bedrock_kwargs)

    pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=3)
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id::text, address, title, dublin_district, property_type, "
            "bedrooms, bathrooms, carpet_area_sqm, ber_rating, heating_type, "
            "price, is_chain_free, is_htb_eligible, is_south_facing, "
            "days_on_market, estate_agent, description, management_fee_eur "
            "FROM properties WHERE embedding_id IS NULL AND is_active = true "
            "ORDER BY created_at DESC"
        )

    print(f"Found {len(rows)} properties without embeddings.")
    success = 0
    failed = 0

    for row in rows:
        prop_dict = dict(row)
        prop_id = prop_dict["id"]
        try:
            text = _build_text(prop_dict)
            embedding = _embed(text, bedrock)

            doc = {
                "property_id": prop_id,
                "text_content": text,
                "embedding": embedding,
                "price": prop_dict.get("price"),
                "bedrooms": prop_dict.get("bedrooms"),
                "bathrooms": prop_dict.get("bathrooms"),
                "carpet_area_sqm": prop_dict.get("carpet_area_sqm"),
                "dublin_district": prop_dict.get("dublin_district"),
                "property_type": prop_dict.get("property_type"),
                "heating_type": prop_dict.get("heating_type"),
                "is_chain_free": prop_dict.get("is_chain_free") or False,
                "is_htb_eligible": prop_dict.get("is_htb_eligible") or False,
                "is_south_facing": prop_dict.get("is_south_facing") or False,
                "estate_agent": prop_dict.get("estate_agent"),
                "days_on_market": prop_dict.get("days_on_market"),
                "management_fee_eur": prop_dict.get("management_fee_eur"),
                "is_active": True,
            }
            await _upsert_os(prop_id, doc)

            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE properties SET embedding_id = $2 WHERE id = $1::uuid",
                    prop_id, prop_id,
                )
            success += 1
            print(f"  ✓  {prop_dict.get('address') or prop_id}")
        except Exception as e:
            failed += 1
            print(f"  ✗  {prop_dict.get('address') or prop_id}: {e}")

    await pool.close()
    print(f"\nDone — {success} embedded, {failed} failed.")


if __name__ == "__main__":
    asyncio.run(backfill())
