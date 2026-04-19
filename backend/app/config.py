from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    database_url: str = "postgresql+asyncpg://property_user:property_pass@localhost:5432/property_sahi"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # AWS
    aws_default_region: str = "eu-west-1"
    aws_access_key_id: str = "test"
    aws_secret_access_key: str = "test"
    use_localstack: bool = True

    # OpenSearch
    opensearch_endpoint: str = "http://localhost:4566"
    opensearch_index: str = "properties-v1"

    # Bedrock
    bedrock_llm_model_id: str = "anthropic.claude-sonnet-4-5"
    bedrock_embedding_model_id: str = "amazon.titan-embed-text-v2:0"

    # Decision Hub (dhub) - PyMC skill
    dhub_base_url: str = "https://hub.decision.ai"
    dhub_pymc_skill_path: str = "/skills/pymc-labs/pymc-modeling"
    dhub_api_key: str = ""

    # Google Maps
    google_maps_api_key: str = ""

    # Security
    api_key: str = "change-me-in-production"

    # S3
    model_cache_bucket: str = "property-sahi-model-cache"

    # Substack
    substack_publication_url: str = ""
    substack_api_key: str = ""

    # App
    app_env: str = "development"
    log_level: str = "INFO"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


settings = Settings()
