from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, Request

from backend.auth.password import hash_password
from backend.auth.session import COOKIE_NAME
from backend.deps import require_admin
from backend.errors import AdminOperationError, ResourceNotFoundError
from backend.schemas import (
    AdminOverview,
    AdminTimeseries,
    AdminUserDetail,
    AdminUserList,
    ResetPasswordRequest,
    SetRoleRequest,
    User,
)
from shared import storage

router = APIRouter(prefix="/admin", tags=["admin"])


def _require_target(user_id: str) -> User:
    target = storage.get_user_by_id(user_id)
    if target is None:
        raise ResourceNotFoundError("user not found")
    return target


@router.get("/users", response_model=AdminUserList)
async def list_users(q: str = "", limit: int = 50, offset: int = 0, _: User = Depends(require_admin)) -> AdminUserList:
    items = storage.list_users(q=q, limit=limit, offset=offset)
    return AdminUserList(items=items, total=storage.count_users(q=q))


@router.get("/users/{user_id}", response_model=AdminUserDetail)
async def user_detail(user_id: str, request: Request, _: User = Depends(require_admin)) -> AdminUserDetail:
    target = _require_target(user_id)
    counts = storage.get_user_counts(user_id)
    cookie = request.cookies.get(COOKIE_NAME)
    return AdminUserDetail(
        id=target.id,
        username=target.username,
        created_at=target.created_at,
        role=target.role,
        status=target.status,
        paper_count=counts["paper_count"],
        attempt_count=counts["attempt_count"],
        correct_rate=storage.user_correct_rate(user_id),
        membership_expires_at=_fetch_membership_expiry(user_id, cookie),
    )


@router.post("/users/{user_id}/role", response_model=User)
async def set_role(user_id: str, body: SetRoleRequest, admin: User = Depends(require_admin)) -> User:
    if user_id == admin.id:
        raise AdminOperationError("cannot change your own role")
    _require_target(user_id)
    storage.set_user_role(user_id, body.role)
    return storage.get_user_by_id(user_id)


@router.post("/users/{user_id}/reset-password", response_model=User)
async def reset_password(user_id: str, body: ResetPasswordRequest, _: User = Depends(require_admin)) -> User:
    _require_target(user_id)
    storage.update_password_hash(user_id, hash_password(body.new_password))
    storage.delete_sessions_by_user(user_id)
    return storage.get_user_by_id(user_id)


@router.post("/users/{user_id}/ban", response_model=User)
async def ban(user_id: str, admin: User = Depends(require_admin)) -> User:
    if user_id == admin.id:
        raise AdminOperationError("cannot ban yourself")
    _require_target(user_id)
    storage.set_user_status(user_id, "banned")
    storage.delete_sessions_by_user(user_id)
    return storage.get_user_by_id(user_id)


@router.post("/users/{user_id}/unban", response_model=User)
async def unban(user_id: str, _: User = Depends(require_admin)) -> User:
    _require_target(user_id)
    storage.set_user_status(user_id, "active")
    return storage.get_user_by_id(user_id)


def _payment_base() -> str:
    return "http://localhost:8001"


@router.get("/stats/overview", response_model=AdminOverview)
async def stats_overview(request: Request, _: User = Depends(require_admin)) -> AdminOverview:
    counts = storage.admin_counts()
    cookie = request.cookies.get(COOKIE_NAME)
    return AdminOverview(**counts, active_members=_fetch_active_members(cookie))


@router.get("/stats/timeseries", response_model=AdminTimeseries)
async def stats_timeseries(days: int = 30, _: User = Depends(require_admin)) -> AdminTimeseries:
    return AdminTimeseries(
        users_by_day=storage.users_created_by_day(days),
        papers_by_day=storage.papers_created_by_day(days),
    )


def _fetch_active_members(cookie: str | None) -> int | None:
    # Best-effort cross-service read; payment down → None (non-blocking).
    # Forwards the acting admin's session cookie so payment's require_admin passes.
    try:
        resp = httpx.get(
            f"{_payment_base()}/payapi/admin/memberships?limit=100000",
            cookies={COOKIE_NAME: cookie} if cookie else None,
            timeout=3.0,
        )
        if resp.status_code == 200:
            items = resp.json().get("items", [])
            return sum(1 for m in items if m.get("active"))
    except httpx.HTTPError:
        return None
    return None


def _fetch_membership_expiry(user_id: str, cookie: str | None) -> str | None:
    # Best-effort cross-service read; payment down → None (non-blocking).
    # Forwards the acting admin's session cookie so payment's require_admin passes.
    try:
        resp = httpx.get(
            f"{_payment_base()}/payapi/admin/memberships/{user_id}",
            cookies={COOKIE_NAME: cookie} if cookie else None,
            timeout=3.0,
        )
        if resp.status_code == 200:
            return resp.json().get("expires_at")
    except httpx.HTTPError:
        return None
    return None
