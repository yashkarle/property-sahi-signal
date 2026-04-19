import json
from typing import Any

from app.config import settings
from app.core.bedrock import get_bedrock_runtime


def build_property_embedding_text(prop: dict[str, Any]) -> str:
    parts = [
        prop.get("address", ""),
        prop.get("dublin_district", ""),
        f"{prop.get('property_type', '')} with {prop.get('bedrooms', '?')} bedrooms "
        f"and {prop.get('bathrooms', '?')} bathrooms",
    ]
    if prop.get("carpet_area_sqm"):
        parts.append(f"{prop['carpet_area_sqm']}sqm carpet area")
    if prop.get("ber_rating"):
        parts.append(f"BER {prop['ber_rating']}")
    if prop.get("heating_type"):
        parts.append(f"{prop['heating_type']} heating")
    if prop.get("seller_status"):
        parts.append(prop["seller_status"])
    if prop.get("days_on_market") is not None:
        parts.append(f"{prop['days_on_market']} days on market")
    if prop.get("description"):
        parts.append(prop["description"][:500])
    return ". ".join(filter(None, parts))


def embed_text(text: str) -> list[float]:
    client = get_bedrock_runtime()
    response = client.invoke_model(
        modelId=settings.bedrock_embedding_model_id,
        body=json.dumps({"inputText": text}),
        contentType="application/json",
    )
    result = json.loads(response["body"].read())
    return result["embedding"]


def embed_texts_batch(texts: list[str]) -> list[list[float]]:
    return [embed_text(t) for t in texts]
