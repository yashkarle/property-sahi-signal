import time
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import get_cached, set_cached
from app.core.embeddings import build_property_embedding_text, embed_text
from app.core.opensearch import BER_CODE, knn_search
from app.models.property import Property
from app.schemas.search import SearchFilters, SearchRequest


async def semantic_search(
    request: SearchRequest,
    db: AsyncSession,
) -> dict:
    t0 = time.perf_counter()

    cache_key = {"query": request.query, "filters": request.filters.model_dump(), "offset": request.offset}
    cached = await get_cached("search", cache_key)
    if cached:
        cached["query_time_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        cached["from_cache"] = True
        return cached

    embedding = embed_text(request.query)

    os_filters = _build_opensearch_filters(request.filters)
    os_results = await knn_search(embedding, os_filters, k=request.limit + request.offset)
    property_ids = [r["property_id"] for r in os_results]

    if not property_ids:
        return {"results": [], "total": 0, "search_id": str(uuid.uuid4()), "query_time_ms": round((time.perf_counter() - t0) * 1000, 1)}

    result = await db.execute(
        select(Property).where(Property.id.in_([uuid.UUID(pid) for pid in property_ids]))
    )
    props_by_id = {str(p.id): p for p in result.scalars().all()}

    ordered = [props_by_id[pid] for pid in property_ids if pid in props_by_id]
    page = ordered[request.offset: request.offset + request.limit]

    from app.schemas.property import PropertySummary
    results = [PropertySummary.model_validate(p) for p in page]
    result_dicts = [r.model_dump(mode="json") for r in results]

    response = {
        "results": result_dicts,
        "total": len(ordered),
        "search_id": str(uuid.uuid4()),
        "query_time_ms": round((time.perf_counter() - t0) * 1000, 1),
    }
    await set_cached("search", cache_key, response)
    return response


def _build_opensearch_filters(filters: SearchFilters) -> dict:
    f: dict = {}
    if filters.price_min or filters.price_max:
        f["price"] = {}
        if filters.price_min:
            f["price"]["gte"] = filters.price_min
        if filters.price_max:
            f["price"]["lte"] = filters.price_max
    if filters.bedrooms_min:
        f["bedrooms"] = {"gte": filters.bedrooms_min}
    if filters.bathrooms_min:
        f["bathrooms"] = {"gte": filters.bathrooms_min}
    if filters.carpet_area_sqm_min:
        f["carpet_area_sqm"] = {"gte": filters.carpet_area_sqm_min}
    if filters.property_types:
        f["property_type"] = filters.property_types
    if filters.dublin_districts:
        f["dublin_district"] = filters.dublin_districts
    if filters.is_chain_free is not None:
        f["is_chain_free"] = filters.is_chain_free
    if filters.is_htb_eligible is not None:
        f["is_htb_eligible"] = filters.is_htb_eligible
    if filters.days_on_market_max:
        f["days_on_market"] = {"lte": filters.days_on_market_max}
    if filters.exclude_electric_storage:
        # Handled via must_not in OpenSearch — pass as special key
        f["_exclude_electric_storage"] = True
    if filters.ber_ratings:
        f["ber_rating_code"] = {"lte": max(BER_CODE.get(r, 15) for r in filters.ber_ratings)}
    return f
