from functools import lru_cache
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


def _parse_list(value: str | list[str]) -> list[str]:
    if isinstance(value, list):
        return value
    stripped = value.strip()
    if stripped.startswith("["):
        import json

        parsed = json.loads(stripped)
        return [str(item).strip() for item in parsed]
    return [item.strip() for item in stripped.split(",") if item.strip()]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "AgentCare"
    environment: str = "development"

    database_url: str = Field(
        default="postgresql+psycopg://agentcare:agentcare_dev_password@db:5432/agentcare"
    )

    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"
    groq_model_fast: str = "openai/gpt-oss-20b"

    jwt_secret_key: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    upload_dir: str = "/app/uploads"
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000"]

    run_live_llm_tests: bool = False

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return _parse_list(value)
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()