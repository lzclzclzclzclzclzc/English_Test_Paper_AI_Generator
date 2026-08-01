from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends

from backend.auth.password import hash_password
from backend.deps import require_admin
from backend.errors import AdminOperationError, ResourceNotFoundError
from backend.schemas import (
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
async def user_detail(user_id: str, _: User = Depends(require_admin)) -> AdminUserDetail:
    target = _require_target(user_id)
    rows = storage.list_users(q=target.username, limit=100, offset=0)
    counts = next((r for r in rows if r["id"] == user_id), {"paper_count": 0, "attempt_count": 0})
    return AdminUserDetail(
        id=target.id,
        username=target.username,
        created_at=target.created_at,
        role=target.role,
        status=target.status,
        paper_count=counts["paper_count"],
        attempt_count=counts["attempt_count"],
        correct_rate=storage.user_correct_rate(user_id),
        membership_expires_at=_fetch_membership_expiry(user_id),
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


def _fetch_membership_expiry(user_id: str) -> str | None:
    # Best-effort cross-service read; payment down → None (non-blocking).
    # Task C3 upgrades this to forward the admin's session cookie.
    try:
        resp = httpx.get(f"{_payment_base()}/payapi/admin/memberships/{user_id}", timeout=3.0)
        if resp.status_code == 200:
            return resp.json().get("expires_at")
    except httpx.HTTPError:
        return None
    return None
