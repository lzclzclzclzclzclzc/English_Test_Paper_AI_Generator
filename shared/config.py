from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field
from dotenv import load_dotenv


class StorageConfig(BaseModel):
    sqlite_path: Path = Path("data/questions.db")
    chroma_path: Path = Path("data/chroma")


class BackendConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8000
    env: Literal["development", "production", "test"] = "development"
    session_ttl_days: int = 30
    bcrypt_rounds: int = 12
    static_dir: Path = Path("backend/static")
    rate_limit_generate_per_min: int = 30
    rate_limit_solutions_per_min: int = 60


class LLMConfig(BaseModel):
    api_key: str = ""
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-chat"
    max_concurrency: int = 4
    max_retries: int = 3


class AppConfig(BaseModel):
    storage: StorageConfig = Field(default_factory=StorageConfig)
    backend: BackendConfig = Field(default_factory=BackendConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    llm_trace_full: bool = False


@lru_cache(maxsize=1)
def get_config() -> AppConfig:
    # Environment variables supplied by deployment always win over .env, so
    # local development remains convenient without weakening production config.
    load_dotenv(".env", override=False)
    return AppConfig(
        storage=StorageConfig(
            sqlite_path=Path(os.getenv("SQLITE_PATH", "data/questions.db")),
            chroma_path=Path(os.getenv("CHROMA_PATH", "data/chroma")),
        ),
        backend=BackendConfig(
            host=os.getenv("BACKEND_HOST", "127.0.0.1"),
            port=int(os.getenv("BACKEND_PORT", "8000")),
            env=os.getenv("BACKEND_ENV", "development"),  # type: ignore[arg-type]
            session_ttl_days=int(os.getenv("SESSION_TTL_DAYS", "30")),
            bcrypt_rounds=int(os.getenv("BCRYPT_ROUNDS", "12")),
            static_dir=Path(os.getenv("BACKEND_STATIC_DIR", "backend/static")),
            rate_limit_generate_per_min=int(os.getenv("RATE_LIMIT_GENERATE_PER_MIN", "30")),
            rate_limit_solutions_per_min=int(os.getenv("RATE_LIMIT_SOLUTIONS_PER_MIN", "60")),
        ),
        llm=LLMConfig(
            api_key=os.getenv("LLM_API_KEY", ""),
            base_url=os.getenv("LLM_BASE_URL", "https://api.deepseek.com"),
            model=os.getenv("LLM_MODEL", "deepseek-chat"),
            max_concurrency=int(os.getenv("LLM_MAX_CONCURRENCY", "4")),
            max_retries=int(os.getenv("LLM_MAX_RETRIES", "3")),
        ),
        llm_trace_full=os.getenv("LLM_TRACE_FULL", "0") == "1",
    )


def reset_config_cache() -> None:
    get_config.cache_clear()
