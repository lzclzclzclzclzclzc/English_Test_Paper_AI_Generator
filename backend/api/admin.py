from __future__ import annotations

import os

import httpx
from fastapi import APIRouter, Depends, Request

from backend.auth.password import hash_password
from backend.auth.session import COOKIE_NAME
from backend.deps import require_admin
from backend.errors import AdminOperationError, PaymentUpstreamError, ResourceNotFoundError
from backend.schemas import (
    AdminAnalytics,
    AdminAuditItem,
    AdminAuditList,
    AdminMembershipItem,
    AdminMembershipListView,
    AdminOrderItem,
    AdminOrderListView,
    AdminOverview,
    AdminPlanRevenue,
    AdminRevenue,
    AdminRevenueDayPoint,
    AdminSystemHealth,
    AdminTimeseries,
    AdminUserAnalytics,
    AdminUserAttemptItem,
    AdminUserAttemptList,
    AdminUserDetail,
    AdminUserList,
    AdminUserPaperItem,
    AdminUserPaperList,
    GrantByUsernameRequest,
    GrantDaysRequest,
    QuestionBankChapterStat,
    QuestionBankKpStat,
    QuestionBankList,
    QuestionBankListItem,
    QuestionBankStats,
    QuestionBankTypeStat,
    ResetPasswordRequest,
    SetRoleRequest,
    User,
)
from backend.services import ai_gateway
from shared import storage
from shared.config import get_config
from shared.schemas import MasteryProfile

router = APIRouter(prefix="/admin", tags=["admin"])


def _require_target(user_id: str) -> User:
    target = storage.get_user_by_id(user_id)
    if target is None:
        raise ResourceNotFoundError("user not found")
    return target


def admin_cookie(request: Request) -> str | None:
    """The acting admin's session cookie, forwarded on cross-service payment
    reads so payment's require_admin passes. Centralises the extraction the
    payment-calling endpoints all need."""
    return request.cookies.get(COOKIE_NAME)


@router.get("/users", response_model=AdminUserList)
async def list_users(
    q: str = "",
    limit: int = 50,
    offset: int = 0,
    status: str = "",
    sort: str = "created_at",
    _: User = Depends(require_admin),
) -> AdminUserList:
    items = storage.list_users(q=q, limit=limit, offset=offset, status=status, sort=sort)
    return AdminUserList(items=items, total=storage.count_users(q=q, status=status))


@router.get("/users/{user_id}", response_model=AdminUserDetail)
def user_detail(user_id: str, cookie: str | None = Depends(admin_cookie), _: User = Depends(require_admin)) -> AdminUserDetail:
    target = _require_target(user_id)
    counts = storage.get_user_counts(user_id)
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


@router.get("/users/{user_id}/mastery", response_model=MasteryProfile)
def user_mastery(user_id: str, _: User = Depends(require_admin)) -> MasteryProfile:
    """That user's knowledge-point mastery profile (read-only, no LLM) — the
    individual-user learning picture behind the admin detail page."""
    _require_target(user_id)
    return ai_gateway.build_profile(user_id)


@router.get("/users/{user_id}/analytics", response_model=AdminUserAnalytics)
def user_analytics(
    user_id: str, days: int = 30, _: User = Depends(require_admin)
) -> AdminUserAnalytics:
    """Single-user answering analytics for the admin learner view: per-day
    volume/correct-rate trend + per-type accuracy. days<=0 = all history."""
    _require_target(user_id)
    window = days if days > 0 else None
    return AdminUserAnalytics(
        attempts_by_day=storage.attempts_by_day(days if days > 0 else 3650, user_id=user_id),
        type_accuracy=storage.question_type_accuracy(window, user_id=user_id),
    )


@router.post("/users/{user_id}/role", response_model=User)
async def set_role(user_id: str, body: SetRoleRequest, admin: User = Depends(require_admin)) -> User:
    if user_id == admin.id:
        raise AdminOperationError("cannot change your own role")
    _require_target(user_id)
    storage.set_user_role(user_id, body.role)
    storage.record_admin_action(admin.id, "set_role", user_id, {"role": body.role})
    return storage.get_user_by_id(user_id)


@router.post("/users/{user_id}/reset-password", response_model=User)
async def reset_password(user_id: str, body: ResetPasswordRequest, admin: User = Depends(require_admin)) -> User:
    _require_target(user_id)
    storage.update_password_hash(user_id, hash_password(body.new_password))
    storage.delete_sessions_by_user(user_id)
    # Audit records the occurrence only — never the plaintext password.
    storage.record_admin_action(admin.id, "reset_password", user_id)
    return storage.get_user_by_id(user_id)


@router.post("/users/{user_id}/ban", response_model=User)
async def ban(user_id: str, admin: User = Depends(require_admin)) -> User:
    if user_id == admin.id:
        raise AdminOperationError("cannot ban yourself")
    _require_target(user_id)
    storage.set_user_status(user_id, "banned")
    storage.delete_sessions_by_user(user_id)
    storage.record_admin_action(admin.id, "ban", user_id)
    return storage.get_user_by_id(user_id)


@router.post("/users/{user_id}/unban", response_model=User)
async def unban(user_id: str, admin: User = Depends(require_admin)) -> User:
    _require_target(user_id)
    storage.set_user_status(user_id, "active")
    # Force re-authentication, symmetric with ban / reset-password.
    storage.delete_sessions_by_user(user_id)
    storage.record_admin_action(admin.id, "unban", user_id)
    return storage.get_user_by_id(user_id)


def _payment_base() -> str:
    # Spec H D4: configurable via PAYMENT_SERVICE_URL (resolves the Spec G
    # §0.2.1 localhost hardcode).
    return get_config().backend.payment_service_url.rstrip("/")


@router.get("/users/{user_id}/papers", response_model=AdminUserPaperList)
def user_papers(user_id: str, limit: int = 10, _: User = Depends(require_admin)) -> AdminUserPaperList:
    """Spec H B1: the user's most recent papers (read-only listing)."""
    _require_target(user_id)
    items = [AdminUserPaperItem(**p) for p in storage.list_user_papers(user_id, limit)]
    return AdminUserPaperList(items=items)


@router.get("/users/{user_id}/attempts", response_model=AdminUserAttemptList)
def user_attempts(user_id: str, limit: int = 10, _: User = Depends(require_admin)) -> AdminUserAttemptList:
    """Spec H B2: the user's recent attempts with per-paper rollup."""
    _require_target(user_id)
    items = [AdminUserAttemptItem(**a) for a in storage.list_user_attempt_summary(user_id, limit)]
    return AdminUserAttemptList(items=items)


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
            trust_env=False,  # local backend→payment call; never route via system proxy
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
            trust_env=False,  # local backend→payment call; never route via system proxy
        )
    except httpx.HTTPError as exc:
        raise PaymentUpstreamError(str(exc)) from exc
    if resp.status_code != 200:
        raise PaymentUpstreamError(f"payment POST {path} -> {resp.status_code}")
    return resp.json()


@router.get("/stats/overview", response_model=AdminOverview)
def stats_overview(cookie: str | None = Depends(admin_cookie), _: User = Depends(require_admin)) -> AdminOverview:
    counts = storage.admin_counts()
    return AdminOverview(
        **counts,
        active_members=_fetch_active_members(cookie),
        total_revenue_cents=_fetch_total_revenue_cents(cookie),
    )


@router.get("/stats/timeseries", response_model=AdminTimeseries)
async def stats_timeseries(days: int = 30, _: User = Depends(require_admin)) -> AdminTimeseries:
    return AdminTimeseries(
        users_by_day=storage.users_created_by_day(days),
        papers_by_day=storage.papers_created_by_day(days),
    )


@router.get("/analytics", response_model=AdminAnalytics)
def stats_analytics(days: int = 30, _: User = Depends(require_admin)) -> AdminAnalytics:
    """Site-wide answering analytics: all-users mastery profile, daily
    volume + correct-rate trend, and per-type accuracy. `days<=0` = all
    history (window_days=None); the trend still needs a finite span, so it
    falls back to a very wide window."""
    window = days if days > 0 else None
    return AdminAnalytics(
        site_mastery=ai_gateway.build_site_profile(window),
        attempts_by_day=storage.attempts_by_day(days if days > 0 else 3650),
        type_accuracy=storage.question_type_accuracy(window),
    )


# ---- membership / order aggregation (enrich payment data with usernames) ----


@router.get("/memberships", response_model=AdminMembershipListView)
def list_memberships(
    q: str = "",
    limit: int = 50,
    offset: int = 0,
    expiring_within_days: int | None = None,
    active: bool | None = None,
    cookie: str | None = Depends(admin_cookie),
    _: User = Depends(require_admin),
) -> AdminMembershipListView:
    # Pull the full membership set from payment, then join usernames locally.
    # expiring_within_days (Spec H D2) is applied upstream in payment;
    # active (also D2) filters the enriched rows locally.
    params: dict = {"limit": 100000}
    if expiring_within_days is not None:
        params["expiring_within_days"] = expiring_within_days
    payload = _payment_get_json("/payapi/admin/memberships", cookie, params=params)
    items = payload.get("items", [])
    name_map = storage.usernames_by_ids([m["user_id"] for m in items])
    # Drop memberships whose user no longer exists locally — the admin list
    # must never show "(已删除/未知)" rows (and the overview's active-member
    # count stays consistent with what this list shows).
    rows = [
        AdminMembershipItem(
            user_id=m["user_id"],
            username=name_map.get(m["user_id"]),
            expires_at=m.get("expires_at"),
            active=bool(m.get("active")),
        )
        for m in items
        if m["user_id"] in name_map
    ]
    if active is not None:
        rows = [r for r in rows if r.active == active]
    if q:
        needle = q.lower()
        # Rows without a resolvable username are excluded when a query is given.
        rows = [r for r in rows if r.username and needle in r.username.lower()]
    total = len(rows)
    page = rows[offset : offset + limit] if limit else rows[offset:]
    return AdminMembershipListView(items=page, total=total)


@router.get("/orders", response_model=AdminOrderListView)
def list_orders(
    status: str = "",
    limit: int = 50,
    offset: int = 0,
    cookie: str | None = Depends(admin_cookie),
    _: User = Depends(require_admin),
) -> AdminOrderListView:
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
    return AdminOrderListView(items=rows, total=payload.get("total", 0))


@router.post("/memberships/grant")
def grant_membership_by_username(
    body: GrantByUsernameRequest, cookie: str | None = Depends(admin_cookie), admin: User = Depends(require_admin)
) -> dict:
    user = storage.get_user_by_username(body.username)
    if user is None:
        raise ResourceNotFoundError("用户不存在")
    result = _payment_post_json(
        f"/payapi/admin/memberships/{user.id}/grant", cookie, json={"days": body.days}
    )
    storage.record_admin_action(admin.id, "grant_membership", user.id, {"days": body.days})
    return result


@router.post("/memberships/{user_id}/grant")
def grant_membership(
    user_id: str, body: GrantDaysRequest, cookie: str | None = Depends(admin_cookie), admin: User = Depends(require_admin)
) -> dict:
    result = _payment_post_json(
        f"/payapi/admin/memberships/{user_id}/grant", cookie, json={"days": body.days}
    )
    storage.record_admin_action(admin.id, "grant_membership", user_id, {"days": body.days})
    return result


@router.post("/memberships/{user_id}/revoke")
def revoke_membership(
    user_id: str, cookie: str | None = Depends(admin_cookie), admin: User = Depends(require_admin)
) -> dict:
    result = _payment_post_json(f"/payapi/admin/memberships/{user_id}/revoke", cookie)
    storage.record_admin_action(admin.id, "revoke_membership", user_id)
    return result


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
    # Only count members whose user still exists locally, so the overview
    # metric matches the (already filtered) memberships list.
    name_map = storage.usernames_by_ids([m["user_id"] for m in items])
    return sum(1 for m in items if m.get("active") and m["user_id"] in name_map)


def _fetch_membership_expiry(user_id: str, cookie: str | None) -> str | None:
    # Best-effort cross-service read; payment down → None (non-blocking).
    # Forwards the acting admin's session cookie so payment's require_admin passes.
    try:
        payload = _payment_get_json(f"/payapi/admin/memberships/{user_id}", cookie)
    except PaymentUpstreamError:
        return None
    return payload.get("expires_at")


def _fetch_total_revenue_cents(cookie: str | None) -> int | None:
    # Best-effort cross-service read; payment down → None (non-blocking).
    try:
        payload = _payment_get_json(
            "/payapi/admin/stats/revenue", cookie, params={"days": 1}
        )
    except PaymentUpstreamError:
        return None
    return payload.get("total_cents")


# ---- question bank (Spec H C, read-only questions.db) ----


@router.get("/questionbank/stats", response_model=QuestionBankStats)
def questionbank_stats(_: User = Depends(require_admin)) -> QuestionBankStats:
    stats = storage.questionbank_stats()
    return QuestionBankStats(
        total=stats["total"],
        by_type=[QuestionBankTypeStat(**t) for t in stats["by_type"]],
        by_knowledge_point=[QuestionBankKpStat(**k) for k in stats["by_knowledge_point"]],
        by_chapter=[QuestionBankChapterStat(**c) for c in stats["by_chapter"]],
    )


@router.get("/questionbank/questions", response_model=QuestionBankList)
def questionbank_questions(
    type: str = "",
    kp: str = "",
    book: str = "",
    chapter: str = "",
    q: str = "",
    limit: int = 20,
    offset: int = 0,
    _: User = Depends(require_admin),
) -> QuestionBankList:
    items, total = storage.questionbank_search(
        question_type=type,
        knowledge_point_id=kp,
        book=book,
        chapter_l1=chapter,
        q=q,
        limit=limit,
        offset=offset,
    )
    return QuestionBankList(items=[QuestionBankListItem(**i) for i in items], total=total)


# ---- revenue / audit / system health (Spec H D) ----


@router.get("/stats/revenue", response_model=AdminRevenue)
def stats_revenue(days: int = 30, cookie: str | None = Depends(admin_cookie), _: User = Depends(require_admin)) -> AdminRevenue:
    payload = _payment_get_json("/payapi/admin/stats/revenue", cookie, params={"days": days})
    return AdminRevenue(
        total_cents=payload.get("total_cents", 0),
        revenue_by_day=[AdminRevenueDayPoint(**d) for d in payload.get("revenue_by_day", [])],
        by_plan=[AdminPlanRevenue(**p) for p in payload.get("by_plan", [])],
    )


@router.get("/audit", response_model=AdminAuditList)
def list_audit(
    actor: str = "",
    action: str = "",
    limit: int = 50,
    offset: int = 0,
    _: User = Depends(require_admin),
) -> AdminAuditList:
    items, total = storage.list_admin_audit(
        actor_user_id=actor, action=action, limit=limit, offset=offset
    )
    return AdminAuditList(items=[AdminAuditItem(**i) for i in items], total=total)


def _probe_http(url: str, timeout: float = 2.0) -> bool:
    """Transport-level reachability probe: any HTTP response counts as up
    (401/404 still prove the service is alive); only transport errors /
    timeouts count as down."""
    try:
        httpx.get(url, timeout=timeout, trust_env=False)
        return True
    except httpx.HTTPError:
        return False


@router.get("/system/health", response_model=AdminSystemHealth)
def system_health(_: User = Depends(require_admin)) -> AdminSystemHealth:
    config = get_config()
    llm_ok = _probe_http(f"{config.llm_base_url.rstrip('/')}/models")
    payment_ok = _probe_http(f"{_payment_base()}/payapi/health")
    try:
        bank_total = storage.questionbank_stats()["total"]
    except Exception:
        bank_total = 0
    db_path = storage.get_db_path()
    app_db_size_kb = int(os.path.getsize(db_path) / 1024) if db_path.is_file() else 0
    return AdminSystemHealth(
        payment=payment_ok,
        llm=llm_ok,
        question_bank_total=bank_total,
        app_db_size_kb=app_db_size_kb,
    )
