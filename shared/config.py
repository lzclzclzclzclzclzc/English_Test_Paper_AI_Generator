"""Application configuration management."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class BackendConfig(BaseModel):
    env: Literal["development", "production", "test"] = "development"
    host: str = "127.0.0.1"
    port: int = 8000
    session_ttl_days: int = 30
    bcrypt_rounds: int = 12
    static_dir: Path = Path("backend/static")
    frontend_origin: str = "http://localhost:5173"
    rate_limit_generate_per_min: int = 30
    rate_limit_solutions_per_min: int = 60
    rate_limit_writing_per_min: int = 10
    payment_service_url: str = "http://127.0.0.1:8001"


class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    data_dir: Path = Path("data")
    db_path: Path = Path("data/questions.db")
    chroma_path: Path = Path("data/chroma")
    kb_tree_path: Path = Path("data/kb/knowledge_tree.json")
    chapters_dir: Path = Path("data/chapters")

    llm_api_key: str = ""
    llm_base_url: str = "https://api.scnet.cn/api/llm/v1"
    llm_model: str = "DeepSeek-V4-Flash"
    llm_max_concurrency: int = 4
    llm_max_retries: int = 3

    max_questions_per_paper: int = 50
    backend: BackendConfig = BackendConfig()


_config: AppConfig | None = None


def get_config() -> AppConfig:
    """Global singleton configuration."""
    global _config
    if _config is None:
        config = AppConfig()
        _config = config.model_copy(
            update={
                "db_path": Path(os.getenv("SQLITE_PATH", config.db_path)),
                "chroma_path": Path(os.getenv("CHROMA_PATH", config.chroma_path)),
                "backend": config.backend.model_copy(
                    update={
                        "env": os.getenv("BACKEND_ENV", config.backend.env),
                        "host": os.getenv("BACKEND_HOST", config.backend.host),
                        "port": int(os.getenv("BACKEND_PORT", config.backend.port)),
                        "session_ttl_days": int(os.getenv("SESSION_TTL_DAYS", config.backend.session_ttl_days)),
                        "bcrypt_rounds": int(os.getenv("BCRYPT_ROUNDS", config.backend.bcrypt_rounds)),
                        "static_dir": Path(os.getenv("BACKEND_STATIC_DIR", config.backend.static_dir)),
                        "frontend_origin": os.getenv("FRONTEND_ORIGIN", config.backend.frontend_origin),
                        "rate_limit_generate_per_min": int(
                            os.getenv("RATE_LIMIT_GENERATE_PER_MIN", config.backend.rate_limit_generate_per_min)
                        ),
                        "rate_limit_solutions_per_min": int(
                            os.getenv("RATE_LIMIT_SOLUTIONS_PER_MIN", config.backend.rate_limit_solutions_per_min)
                        ),
                        "payment_service_url": os.getenv("PAYMENT_SERVICE_URL", config.backend.payment_service_url),
                    }
                ),
            }
        )
    return _config


def reset_config_cache() -> None:
    global _config
    _config = None
