"""AWS Lambda entry point for scheduled property ingestion.

Triggered by EventBridge every 6 hours.
Scrapes Daft.ie + downloads PPR CSV and ingests into Postgres + OpenSearch.
"""
import asyncio
import os
import sys
from datetime import date

# Allow running locally: python ingestion/lambda_handler.py
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import structlog

logger = structlog.get_logger()


async def run_ingestion(event: dict = {}, context=None) -> dict:
    logger.info("ingestion_start")
    results: dict = {"daft": 0, "ppr": 0, "errors": []}

    # 1. Download latest PPR data
    try:
        from ingestion.scrapers.ppr_scraper import download_ppr_csv, filter_dublin_records
        year = date.today().year
        ppr_records = await download_ppr_csv(year)
        dublin_records = filter_dublin_records(ppr_records)
        logger.info("ppr_downloaded", total=len(ppr_records), dublin=len(dublin_records))

        # TODO: upsert to ppr_sales table (requires DB session)
        results["ppr"] = len(dublin_records)
    except Exception as e:
        logger.error("ppr_failed", error=str(e))
        results["errors"].append(f"PPR: {e}")

    # 2. Scrape Daft.ie listings
    try:
        from ingestion.scrapers.daft_scraper import scrape_daft_search
        listings = await scrape_daft_search(
            min_price=int(os.getenv("MIN_PRICE", "200000")),
            max_price=int(os.getenv("MAX_PRICE", "400000")),
            max_pages=int(os.getenv("MAX_PAGES", "5")),
        )
        logger.info("daft_scraped", count=len(listings))

        # TODO: upsert to properties table + compute embeddings
        results["daft"] = len(listings)
    except Exception as e:
        logger.error("daft_failed", error=str(e))
        results["errors"].append(f"Daft: {e}")

    logger.info("ingestion_complete", **results)
    return results


def handler(event: dict, context) -> dict:
    return asyncio.run(run_ingestion(event, context))


if __name__ == "__main__":
    result = asyncio.run(run_ingestion())
    print(result)
