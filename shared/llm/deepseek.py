"""OpenAI-compatible structured LLM client.

Third-party imports are deliberately deferred until first use.  This keeps
offline backend tests and non-AI endpoints usable without an API SDK installed.
"""
from __future__ import annotations

import threading
from typing import TypeVar

from pydantic import BaseModel

from shared.config import LLMConfig, get_config

T = TypeVar("T", bound=BaseModel)


class DeepSeekClient:
    def __init__(self, cfg: LLMConfig | None = None) -> None:
        self._cfg = cfg or get_config().llm
        if not self._cfg.api_key:
            raise RuntimeError("LLM_API_KEY is not configured")
        try:
            import instructor
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("AI dependencies are missing; install requirements.txt") from exc
        raw = OpenAI(api_key=self._cfg.api_key, base_url=self._cfg.base_url)
        self._instructor = instructor.from_openai(raw, mode=instructor.Mode.JSON)
        self._raw = raw
        self._sem = threading.Semaphore(self._cfg.max_concurrency)

    def structured(
        self, *, response_model: type[T], prompt: str, system: str | None = None,
        max_retries: int | None = None, temperature: float = 0.2,
    ) -> T:
        messages = ([{"role": "system", "content": system}] if system else [])
        messages.append({"role": "user", "content": prompt})
        with self._sem:
            return self._instructor.chat.completions.create(
                model=self._cfg.model,
                messages=messages,
                response_model=response_model,
                max_retries=max_retries if max_retries is not None else self._cfg.max_retries,
                temperature=temperature,
                response_format={"type": "json_object"},
            )


_client: DeepSeekClient | None = None


def get_llm_client() -> DeepSeekClient:
    global _client
    if _client is None:
        _client = DeepSeekClient()
    return _client


def reset_llm_client() -> None:
    """Testing hook for changing configuration between test cases."""
    global _client
    _client = None
