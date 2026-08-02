import time
from dataclasses import dataclass

import httpx
from fastapi import Request

from .config import get_settings
from .errors import PaymentError

_CACHE_TTL_SECONDS = 30
_cache: dict[str, tuple["AuthUser", float]] = {}


@dataclass(frozen=True)
class AuthUser:
    id: str
    username: str
    role: str = "user"


async def get_current_user(request: Request) -> AuthUser:
    """解析当前登录用户。

    优先级:
    1. PAYMENT_DEV_FAKE_USER 已设置 → 直接返回假用户(本地联调,不依赖主后端);
    2. 转发 session_id cookie 到主后端 /api/auth/me 校验,结果缓存 30 秒。
    """
    settings = get_settings()
    if settings.payment_dev_fake_user:
        name = settings.payment_dev_fake_user
        return AuthUser(id=f"dev-{name}", username=name, role=settings.payment_dev_fake_role)

    sid = request.cookies.get("session_id")
    if not sid:
        raise PaymentError(401, "auth.unauthorized", "未登录")

    hit = _cache.get(sid)
    if hit and hit[1] > time.monotonic():
        return hit[0]

    try:
        # This is a purely LOCAL call (payment -> main backend, e.g.
        # http://localhost:8000). trust_env=False makes httpx ignore any
        # ambient system/env proxy config; otherwise a machine with a system
        # HTTP proxy would route localhost through the proxy and fail (503).
        async with httpx.AsyncClient(timeout=3.0, trust_env=False) as client:
            resp = await client.get(
                f"{settings.main_backend_url}/api/auth/me",
                cookies={"session_id": sid},
            )
    except httpx.HTTPError:
        raise PaymentError(
            503,
            "payment.auth_upstream_unavailable",
            "主后端不可用,无法校验登录态(本地联调可设置 PAYMENT_DEV_FAKE_USER)",
        )

    if resp.status_code == 401:
        _cache.pop(sid, None)
        raise PaymentError(401, "auth.unauthorized", "登录已过期")
    if resp.status_code != 200:
        raise PaymentError(
            503,
            "payment.auth_upstream_unavailable",
            f"主后端登录校验异常(HTTP {resp.status_code})",
        )

    data = resp.json()
    user = AuthUser(id=str(data["id"]), username=data["username"], role=data.get("role", "user"))
    _cache[sid] = (user, time.monotonic() + _CACHE_TTL_SECONDS)
    return user


async def require_admin(request: Request) -> AuthUser:
    user = await get_current_user(request)
    if user.role != "admin":
        raise PaymentError(403, "auth.forbidden", "无权访问")
    return user
