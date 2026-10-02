from functools import lru_cache
from pathlib import Path
from typing import Literal, Self
from urllib.parse import urlsplit

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


class Settings(BaseSettings):
    app_name: str = "Hybrid Workforce Placement Engine"
    environment: Literal["development", "test", "staging", "production"] = "development"
    api_prefix: str = "/api"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])

    database_url: str = "postgresql+psycopg://workforce:workforce@localhost:5433/workforce"

    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "workforce-password"

    jwt_secret: str = "replace-this-development-secret-before-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    @field_validator("database_url")
    @classmethod
    def normalize_local_database_host(cls, value: str) -> str:
        url = make_url(value)
        if url.host == "localhost":
            return url.set(host="127.0.0.1").render_as_string(hide_password=False)
        return value

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_deployment_settings(self) -> Self:
        if self.environment in {"staging", "production"}:
            if self.jwt_secret == type(self).model_fields["jwt_secret"].default or len(self.jwt_secret.strip()) < 32:
                raise ValueError("Shared deployments require a unique JWT_SECRET of at least 32 characters")
            if not self.cors_origins:
                raise ValueError("Shared deployments require explicit HTTPS CORS_ORIGINS")
            for origin in self.cors_origins:
                parsed = urlsplit(origin)
                if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
                    raise ValueError("CORS_ORIGINS must contain HTTPS origins without paths or credentials")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
