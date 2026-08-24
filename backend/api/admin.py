from __future__ import annotations

import os

import httpx
from fastapi import APIRouter, Depends

from backend.auth.password import hash_password
from backend.deps import require_admin
from backend.errors import AdminOperationError, ResourceNotFoundError
from backend.schemas import (
    AdjustCreditsByUsernameRequest,
    AdjustCreditsRequest,
    AdminAnalytics,
    AdminAuditItem,
    AdminAuditList,
    AdminCreditAccountDetail,
    AdminCreditAccountItem,
    AdminCreditAccountListView,
    AdminOrderItem,
    AdminOrderListView,
    AdminOverview,
    AdminPackRevenue,
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
    CreditLedgerItem,
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
from backend.services import ai_gateway, credits
from backend.services.payment import orders as order_service
from shared import storage
from shared.config import get_config
from shared.schemas import MasteryProfile

router = APIRouter(prefix="/admin", tags=["admin"])


def _require_target(user_id: str) -> User:
    target = storage.get_user_by_id(user_id)
    if target is None:
        raise ResourceNotFoundError("user not found")
    return target



@router.get("/users", response_model=AdminUserList)
async def list_users(
    q: str = "",
    limit: int = 50,
    offset: int = 0,
    status: str = "",
    sort: str = "created_at",
    role: str = "",
    created_from: str = "",
    created_to: str = "",
    _: User = Depends(require_admin),
) -> AdminUserList:
    items = storage.list_users(
        q=q, limit=limit, offset=offset, status=status, sort=sort,
        role=role, created_from=created_from, created_to=created_to,
    )
    total = storage.count_users(
        q=q, status=status, role=role, created_from=created_from, created_to=created_to,
    )
    return AdminUserList(items=items, total=total)


@router.get("/users/{user_id}", response_model=AdminUserDetail)
def user_detail(user_id: str, _: User = Depends(require_admin)) -> AdminUserDetail:
    target = _require_target(user_id)
    counts = storage.get_user_counts(user_id)
    acct = credits.get_account(user_id)
    return AdminUserDetail(
        id=target.id,
        username=target.username,
        created_at=target.created_at,
        role=target.role,
        status=target.status,
        paper_count=counts["paper_count"],
        attempt_count=counts["attempt_count"],
        correct_rate=storage.user_correct_rate(user_id),
        credits_balance=acct.balance,
        credits_daily_balance=acct.daily_balance,
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
    """Single-user answering analytics for the admin user-detail view: per-day
    volume/correct-rate trend + per-type accuracy + per-day vocabulary study
    counts. days<=0 = all history."""
    _require_target(user_id)
    window = days if days > 0 else None
    return AdminUserAnalytics(
        attempts_by_day=storage.attempts_by_day(days if days > 0 else 3650, user_id=user_id),
        type_accuracy=storage.question_type_accuracy(window, user_id=user_id),
        vocabulary_by_day=storage.vocabulary_studied_by_day(days if days > 0 else 3650, user_id=user_id),
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


@router.get("/stats/overview", response_model=AdminOverview)
def stats_overview(_: User = Depends(require_admin)) -> AdminOverview:
    counts = storage.admin_counts()
    revenue = order_service.revenue_stats(days=1)
    return AdminOverview(
        **counts,
        paying_users=order_service.paying_user_count(),
        total_revenue_cents=revenue["total_cents"],
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


# ---- credits / orders (本地账本，2026-08 自 payment 服务合并) ----


@router.get("/credits", response_model=AdminCreditAccountListView)
def list_credit_accounts(
    q: str = "",
    limit: int = 50,
    offset: int = 0,
    _: User = Depends(require_admin),
) -> AdminCreditAccountListView:
    items, total = credits.list_accounts(q, limit=max(1, min(limit, 200)), offset=max(0, offset))
    return AdminCreditAccountListView(items=[AdminCreditAccountItem(**i) for i in items], total=total)


@router.get("/credits/{user_id}", response_model=AdminCreditAccountDetail)
def credit_account_detail(
    user_id: str, limit: int = 50, offset: int = 0, _: User = Depends(require_admin)
) -> AdminCreditAccountDetail:
    target = _require_target(user_id)
    acct = credits.get_account(user_id)
    ledger, total = credits.list_ledger(user_id, limit=max(1, min(limit, 200)), offset=max(0, offset))
    return AdminCreditAccountDetail(
        user_id=user_id,
        username=target.username,
        balance=acct.balance,
        daily_balance=acct.daily_balance,
        daily_grant=acct.daily_grant,
        spent_total=credits.spent_total(user_id),
        ledger=[CreditLedgerItem(**i) for i in ledger],
        ledger_total=total,
    )


def _adjust(admin: User, user_id: str, body: AdjustCreditsRequest) -> AdminCreditAccountItem:
    target = _require_target(user_id)
    if body.delta == 0:
        raise AdminOperationError("delta 不能为 0")
    acct = credits.grant(
        user_id, body.delta, kind=credits.KIND_ADMIN_ADJUST, note=f"管理员 {admin.username}：{body.note}"
    )
    storage.record_admin_action(admin.id, "adjust_credits", user_id, {"delta": body.delta, "note": body.note})
    return AdminCreditAccountItem(
        user_id=user_id,
        username=target.username,
        balance=acct.balance,
        daily_balance=acct.daily_balance,
        daily_date=acct.daily_date,
    )


@router.post("/credits/adjust", response_model=AdminCreditAccountItem)
def adjust_credits_by_username(
    body: AdjustCreditsByUsernameRequest, admin: User = Depends(require_admin)
) -> AdminCreditAccountItem:
    user = storage.get_user_by_username(body.username)
    if user is None:
        raise ResourceNotFoundError("用户不存在")
    return _adjust(admin, user.id, body)


@router.post("/credits/{user_id}/adjust", response_model=AdminCreditAccountItem)
def adjust_credits(
    user_id: str, body: AdjustCreditsRequest, admin: User = Depends(require_admin)
) -> AdminCreditAccountItem:
    return _adjust(admin, user_id, body)


@router.get("/orders", response_model=AdminOrderListView)
def list_orders(
    status: str = "",
    limit: int = 50,
    offset: int = 0,
    order_no: str = "",
    user: str = "",
    pack_id: str = "",
    created_from: str = "",
    created_to: str = "",
    paid_from: str = "",
    paid_to: str = "",
    _: User = Depends(require_admin),
) -> AdminOrderListView:
    items, total = order_service.list_orders(
        status or None, max(1, min(limit, 200)), max(0, offset),
        out_trade_no=order_no, user_q=user, pack_id=pack_id,
        created_from=created_from, created_to=created_to,
        paid_from=paid_from, paid_to=paid_to,
    )
    name_map = storage.usernames_by_ids([o["user_id"] for o in items])
    rows = [
        AdminOrderItem(
            out_trade_no=o["out_trade_no"],
            user_id=o["user_id"],
            username=name_map.get(o["user_id"]),
            pack_id=o["pack_id"],
            amount_cents=o["amount_cents"],
            credits=o["credits"],
            status=o["status"],
            channel=o.get("channel") or "qr",
            created_at=o["created_at"],
            paid_at=o.get("paid_at"),
        )
        for o in items
    ]
    return AdminOrderListView(items=rows, total=total)


@router.post("/orders/reconcile")
def reconcile_orders(admin: User = Depends(require_admin)) -> dict:
    """对账：PAID 订单若缺 purchase 流水则补入账（极端情况下 CAS 与入账之间崩溃）。"""
    fixed = order_service.reconcile_paid_orders()
    if fixed:
        storage.record_admin_action(admin.id, "adjust_credits", None, {"reconciled_orders": fixed})
    return {"reconciled": fixed}


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
def stats_revenue(days: int = 30, _: User = Depends(require_admin)) -> AdminRevenue:
    payload = order_service.revenue_stats(days)
    return AdminRevenue(
        total_cents=payload["total_cents"],
        revenue_by_day=[AdminRevenueDayPoint(**d) for d in payload["revenue_by_day"]],
        by_pack=[AdminPackRevenue(**p) for p in payload["by_pack"]],
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
    try:
        bank_total = storage.questionbank_stats()["total"]
    except Exception:
        bank_total = 0
    db_path = storage.get_db_path()
    app_db_size_kb = int(os.path.getsize(db_path) / 1024) if db_path.is_file() else 0
    return AdminSystemHealth(
        llm=llm_ok,
        payment_mock=config.payment.mock_pay,
        question_bank_total=bank_total,
        app_db_size_kb=app_db_size_kb,
    )
