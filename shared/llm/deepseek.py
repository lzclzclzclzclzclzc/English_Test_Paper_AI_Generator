"""DeepSeek LLM client (OpenAI compatible).

Uses `instructor` for structured JSON output + pydantic validation.
API base: https://api.scnet.cn/api/llm/v1/chat/completions
Model: DeepSeek-V4-Flash
"""
from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any, Type, TypeVar

import instructor
from openai import OpenAI
from pydantic import BaseModel

from shared.config import get_config

T = TypeVar("T", bound=BaseModel)


@dataclass
class LLMConfig:
    api_key: str = ""
    base_url: str = "https://api.scnet.cn/api/llm/v1"
    model: str = "DeepSeek-V4-Flash"
    max_concurrency: int = 4
    max_retries: int = 3


class DeepSeekClient:
    def __init__(self, cfg: LLMConfig | None = None):
        self._cfg = cfg or LLMConfig()
        self._raw = OpenAI(
            api_key=self._cfg.api_key,
            base_url=self._cfg.base_url,
        )
        self._instructor = instructor.from_openai(
            self._raw,
            mode=instructor.Mode.JSON,
        )
        self._sem = threading.Semaphore(self._cfg.max_concurrency)

    def structured(
        self,
        *,
        response_model: Type[T],
        prompt: str,
        system: str | None = None,
        max_retries: int = 3,
        temperature: float = 0.2,
        model: str | None = None,
    ) -> T:
        """Structured LLM call: JSON Mode + pydantic validation + retry on validation failure."""
        with self._sem:
            messages: list[dict[str, str]] = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})

            return self._instructor.chat.completions.create(
                model=model or self._cfg.model,
                messages=messages,
                response_model=response_model,
                max_retries=max_retries,
                temperature=temperature,
                response_format={"type": "json_object"},
            )

    def text(
        self,
        *,
        prompt: str,
        system: str | None = None,
        temperature: float = 0.4,
        model: str | None = None,
    ) -> str:
        """Plain text LLM call (no pydantic validation)."""
        with self._sem:
            messages: list[dict[str, str]] = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})

            resp = self._raw.chat.completions.create(
                model=model or self._cfg.model,
                messages=messages,
                temperature=temperature,
            )
            return resp.choices[0].message.content or ""


_client: DeepSeekClient | None = None


def get_llm_client() -> DeepSeekClient:
    """Global singleton LLM client.
    
    Reads configuration from shared/config.py which loads from .env file.
    """
    global _client
    if _client is None:
        app_cfg = get_config()
        cfg = LLMConfig(
            api_key=app_cfg.llm_api_key,
            base_url=app_cfg.llm_base_url,
            model=app_cfg.llm_model,
            max_concurrency=app_cfg.llm_max_concurrency,
            max_retries=app_cfg.llm_max_retries,
        )
        _client = DeepSeekClient(cfg)
    return _client
