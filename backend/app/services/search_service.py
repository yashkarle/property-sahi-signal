import time
import uuid

from sqlalchemy import or_, select, text
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

    cache_key = {"query": request.query, "filters": request.filters.model_dump(), "offset": request.offset, "limit": request.limit}
    cached = await get_cached("search", cache_key)
    if cached:
        cached["query_time_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        cached["from_cache"] = True
        return cached

    # Try OpenSearch kNN first; fall back to Postgres text search if unavailable
    try:
        embedding = embed_text(request.query)
        os_filters = _build_opensearch_filters(request.filters)
        os_results = await knn_search(embedding, os_filters, k=request.limit + request.offset)
        property_ids = [r["property_id"] for r in os_results]

        if not property_ids:
            return _empty_response(t0)

        result = await db.execute(
            select(Property).where(Property.id.in_([uuid.UUID(pid) for pid in property_ids]))
        )
        props_by_id = {str(p.id): p for p in result.scalars().all()}
        ordered = [props_by_id[pid] for pid in property_ids if pid in props_by_id]
    except Exception:
        # OpenSearch or Bedrock unavailable — fall back to Postgres text search
        ordered = await _postgres_search(request.query, request.filters, db)

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


async def _postgres_search(query: str, filters: SearchFilters, db: AsyncSession) -> list[Property]:
    """Full-text search on Postgres as fallback when OpenSearch is unavailable."""
    stmt = select(Property).where(Property.is_active.is_(True))

    # Text matching across address, description, title
    if query and query.strip():
        terms = query.strip().split()
        text_conditions = []
        for term in terms[:5]:  # cap at 5 terms to avoid slow queries
            like = f"%{term}%"
            text_conditions.append(
                or_(
                    Property.address.ilike(like),
                    Property.description.ilike(like),
                    Property.title.ilike(like),
                    Property.dublin_district.ilike(like),
                    Property.estate_agent.ilike(like),
                )
            )
        if text_conditions:
            stmt = stmt.where(or_(*text_conditions))

    # Apply structured filters
    stmt = _apply_filters(stmt, filters)
    stmt = stmt.order_by(Property.days_on_market.asc().nulls_last(), Property.price.asc().nulls_last())
    stmt = stmt.limit(100)

    result = await db.execute(stmt)
    return list(result.scalars().all())


def _apply_filters(stmt, filters: SearchFilters):
    if filters.price_min:
        stmt = stmt.where(Property.price >= filters.price_min)
    if filters.price_max:
        stmt = stmt.where(Property.price <= filters.price_max)
    if filters.bedrooms_min:
        stmt = stmt.where(Property.bedrooms >= filters.bedrooms_min)
    if filters.bathrooms_min:
        stmt = stmt.where(Property.bathrooms >= filters.bathrooms_min)
    if filters.carpet_area_sqm_min:
        stmt = stmt.where(Property.carpet_area_sqm >= filters.carpet_area_sqm_min)
    if filters.property_types:
        stmt = stmt.where(Property.property_type.in_(filters.property_types))
    if filters.dublin_districts:
        stmt = stmt.where(Property.dublin_district.in_(filters.dublin_districts))
    if filters.is_chain_free is not None:
        stmt = stmt.where(Property.is_chain_free.is_(filters.is_chain_free))
    if filters.is_htb_eligible is not None:
        stmt = stmt.where(Property.is_htb_eligible.is_(filters.is_htb_eligible))
    if filters.days_on_market_max:
        stmt = stmt.where(Property.days_on_market <= filters.days_on_market_max)
    if filters.exclude_electric_storage:
        stmt = stmt.where(
            or_(Property.heating_type != "electric_storage", Property.heating_type.is_(None))
        )
    if filters.ber_ratings:
        stmt = stmt.where(Property.ber_rating.in_(filters.ber_ratings))
    return stmt


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
        f["_exclude_electric_storage"] = True
    if filters.ber_ratings:
        f["ber_rating_code"] = {"lte": max(BER_CODE.get(r, 15) for r in filters.ber_ratings)}
    return f


def _empty_response(t0: float) -> dict:
    return {
        "results": [],
        "total": 0,
        "search_id": str(uuid.uuid4()),
        "query_time_ms": round((time.perf_counter() - t0) * 1000, 1),
    }
