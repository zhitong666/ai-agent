from functools import lru_cache

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    environment: str = Field(
        default="development",
        validation_alias="APP_ENV",
    )
    debug: bool = False

    otel_enabled: bool = True
    otel_service_name: str = "ai-job-agent"
    otel_exporter_otlp_endpoint: str | None = None

    openai_api_key: SecretStr = Field(min_length=1)
    openai_model: str = "deepseek-chat"
    openai_base_url: str = "https://api.deepseek.com"
    llm_max_concurrency: int = 10

    database_url: str = (
        "postgresql://ai_agent:ai_agent@localhost:5432/ai_job_agent"
    )
    redis_url: str = "redis://localhost:6379/0"

    jwt_secret: SecretStr = Field(min_length=32)
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    embedding_model: str = "BAAI/bge-small-zh-v1.5"
    vector_store: str = "chroma"
    qdrant_url: str = "http://localhost:6333"
    rerank_enabled: bool = True
    candidate_top_k: int = 20
    hybrid_alpha: float = 0.5
    hf_endpoint: str = "https://hf-mirror.com"
    hf_home: str = "/app/.cache/huggingface"

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, value: str) -> str:
        allowed = {"development", "test", "staging", "production"}

        if value not in allowed:
            raise ValueError(
                f"environment must be one of {sorted(allowed)}"
            )

        return value

    @field_validator("llm_max_concurrency")
    @classmethod
    def validate_llm_max_concurrency(cls, value: int) -> int:
        if value < 1:
            raise ValueError("llm_max_concurrency must be >= 1")

        return value

    @field_validator("jwt_expire_minutes")
    @classmethod
    def validate_jwt_expire_minutes(cls, value: int) -> int:
        if value < 1:
            raise ValueError("jwt_expire_minutes must be >= 1")

        return value

    @field_validator("vector_store")
    @classmethod
    def validate_vector_store(cls, value: str) -> str:
        allowed = {"chroma", "qdrant"}

        if value not in allowed:
            raise ValueError("vector_store must be chroma or qdrant")

        return value

    @field_validator("candidate_top_k")
    @classmethod
    def validate_candidate_top_k(cls, value: int) -> int:
        if value < 1:
            raise ValueError("candidate_top_k must be >= 1")

        return value

    @field_validator("hybrid_alpha")
    @classmethod
    def validate_hybrid_alpha(cls, value: float) -> float:
        if not 0 <= value <= 1:
            raise ValueError("hybrid_alpha must be between 0 and 1")

        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()