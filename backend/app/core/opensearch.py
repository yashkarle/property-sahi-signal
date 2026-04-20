from typing import Any

from opensearchpy import AsyncOpenSearch, RequestsAWSV4SignerAuth
from opensearchpy.helpers import async_bulk

from app.config import settings

_client: AsyncOpenSearch | None = None

PROPERTIES_INDEX = settings.opensearch_index

PROPERTIES_INDEX_BODY = {
    "settings": {
        "index": {
            "knn": True,
            "knn.algo_param.ef_search": 100,
        }
    },
    "mappings": {
        "properties": {
            "property_id": {"type": "keyword"},
            "embedding": {
                "type": "knn_vector",
                "dimension": 1536,
                "method": {
                    "name": "hnsw",
                    "engine": "faiss",
                    "parameters": {"ef_construction": 128, "m": 16},
                },
            },
            "text_content": {"type": "text"},
            "price": {"type": "integer"},
            "bedrooms": {"type": "integer"},
            "bathrooms": {"type": "integer"},
            "carpet_area_sqm": {"type": "integer"},
            "ber_rating_code": {"type": "integer"},
            "dublin_district": {"type": "keyword"},
            "property_type": {"type": "keyword"},
            "heating_type": {"type": "keyword"},
            "seller_status": {"type": "keyword"},
            "is_chain_free": {"type": "boolean"},
            "is_htb_eligible": {"type": "boolean"},
            "is_south_facing": {"type": "boolean"},
            "days_on_market": {"type": "integer"},
            "management_fee_eur": {"type": "integer"},
            "estate_agent": {"type": "keyword"},
            "year_built": {"type": "integer"},
            "is_active": {"type": "boolean"},
            "location": {"type": "geo_point"},
        }
    },
}

BER_CODE = {
    "A1": 1, "A2": 2, "A3": 3,
    "B1": 4, "B2": 5, "B3": 6,
    "C1": 7, "C2": 8, "C3": 9,
    "D1": 10, "D2": 11,
    "E1": 12, "E2": 13,
    "F": 14, "G": 15,
}


def get_opensearch_client() -> AsyncOpenSearch:
    global _client
    if _client is None:
        if settings.use_localstack:
            _client = AsyncOpenSearch(
                hosts=[settings.opensearch_endpoint],
                use_ssl=False,
                verify_certs=False,
                http_auth=("admin", "admin"),
            )
        else:
            import boto3
            credentials = boto3.Session(
                aws_access_key_id=settings.aws_access_key_id,
                aws_secret_access_key=settings.aws_secret_access_key,
                region_name=settings.aws_default_region,
            ).get_credentials()
            auth = RequestsAWSV4SignerAuth(credentials, settings.aws_default_region, "aoss")
            _client = AsyncOpenSearch(
                hosts=[settings.opensearch_endpoint],
                http_auth=auth,
                use_ssl=True,
                verify_certs=True,
                connection_class=None,
            )
    return _client


async def ensure_index_exists() -> None:
    client = get_opensearch_client()
    exists = await client.indices.exists(index=PROPERTIES_INDEX)
    if not exists:
        await client.indices.create(index=PROPERTIES_INDEX, body=PROPERTIES_INDEX_BODY)


async def upsert_property_document(doc_id: str, document: dict[str, Any]) -> None:
    client = get_opensearch_client()
    await client.index(index=PROPERTIES_INDEX, id=doc_id, body=document, refresh=False)


async def bulk_upsert_documents(docs: list[dict[str, Any]]) -> tuple[int, list[Any]]:
    client = get_opensearch_client()
    actions = [
        {"_index": PROPERTIES_INDEX, "_id": d["property_id"], "_source": d}
        for d in docs
    ]
    return await async_bulk(client, actions, refresh=False)


async def knn_search(
    embedding: list[float],
    filters: dict[str, Any],
    k: int = 50,
) -> list[dict[str, Any]]:
    client = get_opensearch_client()

    filter_clauses: list[dict[str, Any]] = [{"term": {"is_active": True}}]
    for field, value in filters.items():
        if value is None:
            continue
        if isinstance(value, dict):
            filter_clauses.append({"range": {field: value}})
        elif isinstance(value, list):
            filter_clauses.append({"terms": {field: value}})
        else:
            filter_clauses.append({"term": {field: value}})

    query = {
        "size": k,
        "query": {
            "knn": {
                "embedding": {
                    "vector": embedding,
                    "k": k,
                    "filter": {"bool": {"must": filter_clauses}},
                }
            }
        },
        "_source": {"excludes": ["embedding"]},
    }

    response = await client.search(index=PROPERTIES_INDEX, body=query)
    return [hit["_source"] for hit in response["hits"]["hits"]]
