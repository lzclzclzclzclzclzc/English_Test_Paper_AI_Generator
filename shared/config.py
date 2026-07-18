"""Application configuration management."""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings


class AppConfig(BaseSettings):
    data_dir: Path = Path("data")
    db_path: Path = Path("data/questions.db")
    kb_tree_path: Path = Path("data/kb/knowledge_tree.json")
    chapters_dir: Path = Path("data/chapters")

    llm_api_key: str = ""
    llm_base_url: str = "https://api.scnet.cn/api/llm/v1"
    llm_model: str = "DeepSeek-V4-Flash"
    llm_max_concurrency: int = 4
    llm_max_retries: int = 3

    max_questions_per_paper: int = 30

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


_config: AppConfig | None = None


def get_config() -> AppConfig:
    """Global singleton configuration."""
    global _config
    if _config is None:
        _config = AppConfig()
    return _config
