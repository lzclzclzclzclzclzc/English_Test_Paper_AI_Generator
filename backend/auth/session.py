from __future__ import annotations

from fastapi import Response

from shared.config import get_config

COOKIE_NAME = "session_id"


def set_session_cookie(response: Response, session_id: str) -> None:
    config = get_config().backend
    response.set_cookie(
        key=COOKIE_NAME,
        value=session_id,
        httponly=True,
        samesite="strict" if config.env == "production" else "lax",
        secure=config.env == "production",
        max_age=config.session_ttl_days * 24 * 3600,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(key=COOKIE_NAME, path="/")
