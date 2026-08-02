from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, Request

from backend.auth.password import hash_password
from backend.auth.session import COOKIE_NAME
from backend.deps import require_admin
from backend.errors import AdminOperationError, PaymentUpstreamError, ResourceNotFoundError
from backend.schemas import (
    AdminMembershipItem,
    AdminMembershipListView,
    AdminOrderItem,
    AdminOrderListView,
    AdminOverview,
    AdminTimeseries,
    AdminUserDetail,
    AdminUserList,
    GrantByUsernameRequest,
    GrantDaysRequest,
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


def _payment_get_json(path: str, cookie: str | None, params: dict | None = None) -> dict:
    """GET payment JSON, forwarding the admin's session cookie.

    Raises PaymentUpstreamError on any transport failure or non-200 response.
    """
    try:
        resp = httpx.get(
            f"{_payment_base()}{path}",
            params=params,
            cookies={COOKIE_NAME: cookie} if cookie else None,
            timeout=5.0,
        )
    except httpx.HTTPError as exc:
        raise PaymentUpstreamError(str(exc)) from exc
    if resp.status_code != 200:
        raise PaymentUpstreamError(f"payment GET {path} -> {resp.status_code}")
    return resp.json()


def _payment_post_json(path: str, cookie: str | None, json: dict | None = None) -> dict:
    """POST to payment, forwarding the admin's session cookie.

    Raises PaymentUpstreamError on any transport failure or non-200 response.
    """
    try:
        resp = httpx.post(
            f"{_payment_base()}{path}",
            json=json,
            cookies={COOKIE_NAME: cookie} if cookie else None,
            timeout=5.0,
        )
    except httpx.HTTPError as exc:
        raise PaymentUpstreamError(str(exc)) from exc
    if resp.status_code != 200:
        raise PaymentUpstreamError(f"payment POST {path} -> {resp.status_code}")
    return resp.json()


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


# ---- membership / order aggregation (enrich payment data with usernames) ----


@router.get("/memberships", response_model=AdminMembershipListView)
async def list_memberships(
    request: Request,
    q: str = "",
    limit: int = 50,
    offset: int = 0,
    _: User = Depends(require_admin),
) -> AdminMembershipListView:
    cookie = request.cookies.get(COOKIE_NAME)
    # Pull the full membership set from payment, then join usernames locally.
    payload = _payment_get_json(
        "/payapi/admin/memberships", cookie, params={"limit": 100000}
    )
    items = payload.get("items", [])
    name_map = storage.usernames_by_ids([m["user_id"] for m in items])
    rows = [
        AdminMembershipItem(
            user_id=m["user_id"],
            username=name_map.get(m["user_id"]),
            expires_at=m.get("expires_at"),
            active=bool(m.get("active")),
        )
        for m in items
    ]
    if q:
        needle = q.lower()
        # Rows without a resolvable username are excluded when a query is given.
        rows = [r for r in rows if r.username and needle in r.username.lower()]
    total = len(rows)
    page = rows[offset : offset + limit] if limit else rows[offset:]
    return AdminMembershipListView(items=page, total=total)


@router.get("/orders", response_model=AdminOrderListView)
async def list_orders(
    request: Request,
    status: str = "",
    limit: int = 50,
    offset: int = 0,
    _: User = Depends(require_admin),
) -> AdminOrderListView:
    cookie = request.cookies.get(COOKIE_NAME)
    params: dict = {"limit": limit, "offset": offset}
    if status:
        params["status"] = status
    payload = _payment_get_json("/payapi/admin/orders", cookie, params=params)
    items = payload.get("items", [])
    name_map = storage.usernames_by_ids([o["user_id"] for o in items])
    rows = [
        AdminOrderItem(
            out_trade_no=o["out_trade_no"],
            user_id=o["user_id"],
            username=name_map.get(o["user_id"]),
            plan_id=o["plan_id"],
            amount_cents=o["amount_cents"],
            status=o["status"],
            created_at=o["created_at"],
            paid_at=o.get("paid_at"),
        )
        for o in items
    ]
    return AdminOrderListView(items=rows)


@router.post("/memberships/grant")
async def grant_membership_by_username(
    body: GrantByUsernameRequest, request: Request, _: User = Depends(require_admin)
) -> dict:
    user = storage.get_user_by_username(body.username)
    if user is None:
        raise ResourceNotFoundError("用户不存在")
    cookie = request.cookies.get(COOKIE_NAME)
    return _payment_post_json(
        f"/payapi/admin/memberships/{user.id}/grant", cookie, json={"days": body.days}
    )


@router.post("/memberships/{user_id}/grant")
async def grant_membership(
    user_id: str, body: GrantDaysRequest, request: Request, _: User = Depends(require_admin)
) -> dict:
    cookie = request.cookies.get(COOKIE_NAME)
    return _payment_post_json(
        f"/payapi/admin/memberships/{user_id}/grant", cookie, json={"days": body.days}
    )


@router.post("/memberships/{user_id}/revoke")
async def revoke_membership(
    user_id: str, request: Request, _: User = Depends(require_admin)
) -> dict:
    cookie = request.cookies.get(COOKIE_NAME)
    return _payment_post_json(f"/payapi/admin/memberships/{user_id}/revoke", cookie)


def _fetch_active_members(cookie: str | None) -> int | None:
    # Best-effort cross-service read; payment down → None (non-blocking).
    # Forwards the acting admin's session cookie so payment's require_admin passes.
    try:
        payload = _payment_get_json(
            "/payapi/admin/memberships", cookie, params={"limit": 100000}
        )
    except PaymentUpstreamError:
        return None
    items = payload.get("items", [])
    return sum(1 for m in items if m.get("active"))


def _fetch_membership_expiry(user_id: str, cookie: str | None) -> str | None:
    # Best-effort cross-service read; payment down → None (non-blocking).
    # Forwards the acting admin's session cookie so payment's require_admin passes.
    try:
        payload = _payment_get_json(f"/payapi/admin/memberships/{user_id}", cookie)
    except PaymentUpstreamError:
        return None
    return payload.get("expires_at")
