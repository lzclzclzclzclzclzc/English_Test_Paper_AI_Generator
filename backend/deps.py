from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

from fastapi import Cookie, Depends

from backend.auth.session import COOKIE_NAME
from backend.errors import AuthenticationError, RateLimitError
from shared import storage
from shared.config import get_config
from shared.schemas import User

_rate_windows: dict[tuple[str, str], deque[datetime]] = defaultdict(deque)
RATE_LIMIT_WINDOW = timedelta(minutes=1)


async def current_user(session_id: str | None = Cookie(default=None, alias=COOKIE_NAME)) -> User:
    if not session_id:
        raise AuthenticationError("missing session cookie")
    session = storage.get_session(session_id)
    if not session:
        raise AuthenticationError("invalid or expired session")
    user = storage.get_user_by_id(session.user_id)
    if not user:
        storage.delete_session(session_id)
        raise AuthenticationError("session user not found")
    storage.slide_session(session_id, get_config().backend.session_ttl_days)
    return user


def rate_limiter(kind: str, limit_attr: str):
    async def dependency(user: User = Depends(current_user)) -> User:
        config = get_config().backend
        limit = int(getattr(config, limit_attr))
        check_rate_limit(user.id, kind, limit)
        return user

    return dependency


def check_rate_limit(user_id: str, kind: str, limit: int, now: datetime | None = None) -> None:
    now = now or datetime.now(timezone.utc)
    prune_rate_limits(now)
    key = (user_id, kind)
    bucket = _rate_windows[key]
    if len(bucket) >= limit:
        raise RateLimitError()
    bucket.append(now)


def prune_rate_limits(now: datetime | None = None) -> None:
    now = now or datetime.now(timezone.utc)
    window_start = now - RATE_LIMIT_WINDOW
    empty_keys: list[tuple[str, str]] = []
    for key, bucket in _rate_windows.items():
        while bucket and bucket[0] < window_start:
            bucket.popleft()
        if not bucket:
            empty_keys.append(key)
    for key in empty_keys:
        del _rate_windows[key]


def reset_rate_limits() -> None:
    _rate_windows.clear()
