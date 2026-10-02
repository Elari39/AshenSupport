from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_prefix="ASHEN_")
    database_url: str = "sqlite:///./support.db"
    origin: str = "http://localhost:5173"
    secure_cookie: bool = False
    provider: Literal["fake", "online"] = "fake"
    chat_url: str = ""
    chat_key: str = ""
    chat_model: str = ""
    embedding_url: str = ""
    embedding_key: str = ""
    embedding_model: str = ""
    embedding_dimensions: int = Field(default=128, ge=8, le=4096)
    embedding_batch_size: int = Field(default=8, ge=1, le=32)
    rerank_url: str = ""
    rerank_key: str = ""
    rerank_model: str = ""
    retrieval_mode: Literal["vector", "hybrid", "rerank"] = "vector"
    health_targets: dict[str, str] = Field(default_factory=dict)
    session_tasks: int = 5
    ip_tasks: int = 20
    daily_calls: int = 500
    input_price_per_million: float | None = None
    output_price_per_million: float | None = None
    lease_seconds: int = 30

    @model_validator(mode="after")
    def validate_online(self):
        if self.provider == "online" and not all(
            [
                self.chat_url,
                self.chat_key,
                self.chat_model,
                self.embedding_url,
                self.embedding_key,
                self.embedding_model,
            ]
        ):
            raise ValueError("Online provider requires explicit chat and embedding configuration")
        return self


@lru_cache
def settings() -> Settings:
    return Settings()
