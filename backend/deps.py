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
        key = (user.id, kind)
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(minutes=1)
        bucket = _rate_windows[key]
        while bucket and bucket[0] < window_start:
            bucket.popleft()
        if len(bucket) >= limit:
            raise RateLimitError()
        bucket.append(now)
        return user

    return dependency
