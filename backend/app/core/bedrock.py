import json
from typing import Any

import boto3
from botocore.config import Config

from app.config import settings

_bedrock_runtime: Any = None


def get_bedrock_runtime() -> Any:
    global _bedrock_runtime
    if _bedrock_runtime is None:
        kwargs: dict[str, Any] = {
            "service_name": "bedrock-runtime",
            "region_name": settings.aws_default_region,
            "config": Config(retries={"max_attempts": 3, "mode": "adaptive"}),
        }
        if settings.use_localstack:
            kwargs["endpoint_url"] = settings.opensearch_endpoint
            kwargs["aws_access_key_id"] = settings.aws_access_key_id
            kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
        _bedrock_runtime = boto3.client(**kwargs)
    return _bedrock_runtime


def invoke_claude(
    prompt: str,
    system: str = "",
    max_tokens: int = 4096,
    temperature: float = 0.3,
) -> str:
    client = get_bedrock_runtime()
    body: dict[str, Any] = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = system

    response = client.invoke_model(
        modelId=settings.bedrock_llm_model_id,
        body=json.dumps(body),
        contentType="application/json",
    )
    result = json.loads(response["body"].read())
    return result["content"][0]["text"]


def invoke_claude_streaming(
    prompt: str,
    system: str = "",
    max_tokens: int = 4096,
) -> Any:
    client = get_bedrock_runtime()
    body: dict[str, Any] = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = system

    return client.invoke_model_with_response_stream(
        modelId=settings.bedrock_llm_model_id,
        body=json.dumps(body),
        contentType="application/json",
    )
