"""Compute Titan embeddings and upsert to OpenSearch."""
import json
from typing import Any

import boto3

BEDROCK_REGION = "eu-west-1"
EMBEDDING_MODEL = "amazon.titan-embed-text-v2:0"


def get_bedrock_client(use_localstack: bool = True, endpoint: str = "http://localhost:4566") -> Any:
    kwargs: dict[str, Any] = {
        "service_name": "bedrock-runtime",
        "region_name": BEDROCK_REGION,
        "aws_access_key_id": "test",
        "aws_secret_access_key": "test",
    }
    if use_localstack:
        kwargs["endpoint_url"] = endpoint
    return boto3.client(**kwargs)


def embed_property_text(text: str, client: Any) -> list[float]:
    response = client.invoke_model(
        modelId=EMBEDDING_MODEL,
        body=json.dumps({"inputText": text}),
        contentType="application/json",
    )
    result = json.loads(response["body"].read())
    return result["embedding"]


def build_opensearch_document(
    property_id: str,
    text: str,
    embedding: list[float],
    metadata: dict[str, Any],
) -> dict[str, Any]:
    return {
        "property_id": property_id,
        "text_content": text,
        "embedding": embedding,
        **metadata,
    }
