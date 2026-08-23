"""积分账本：账户、扣费、退款、入账（docs/credits-design.md §2）。

设计要点
- 两个桶：`daily`（每日赠送，当日有效，惰性重置）先扣，`balance`（付费 / 注册赠送 /
  管理员调整，不过期）后扣。
- 所有写操作都在一个 `BEGIN IMMEDIATE` 事务里完成（读余额 → 判断 → 写流水 →
  更新账户），SQLite 写锁保证同一用户的并发扣费不会超扣。
- 幂等靠 `credit_ledger` 的唯一索引 (kind, ref_type, ref_id, bucket)：同一次扣费 /
  退款 / 同一订单入账只会落一次；重复调用直接返回既有结果。
- 日界用 Asia/Shanghai（与背单词每日额度同一时区常量）。
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone

from backend.errors import InsufficientCreditsError
from shared import storage
from shared.config import get_config

DAILY_TZ = storage.VOCABULARY_TIMEZONE

KIND_SIGNUP_BONUS = "signup_bonus"
KIND_DAILY_GRANT = "daily_grant"
KIND_PURCHASE = "purchase"
KIND_SPEND = "spend"
KIND_REFUND = "refund"
KIND_ADMIN_ADJUST = "admin_adjust"
KIND_MIGRATE_MEMBERSHIP = "migrate_membership"


@dataclass(frozen=True)
class Account:
    user_id: str
    balance: int
    daily_balance: int
    daily_date: str | None
    daily_grant: int

    @property
    def total(self) -> int:
        return self.balance + self.daily_balance


@dataclass(frozen=True)
class Receipt:
    """一次扣费的结果（也用于幂等重放时返回既有扣费）。"""

    cost: int
    from_daily: int
    from_balance: int
    balance_after: int
    daily_after: int
    duplicate: bool = False


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def today_key(now: datetime | None = None) -> str:
    return (now or datetime.now(timezone.utc)).astimezone(DAILY_TZ).date().isoformat()


# ---- account ---------------------------------------------------------------


def _load_account(conn: sqlite3.Connection, user_id: str, *, now: datetime | None = None) -> Account:
    """读账户；不存在则建；daily_date 不是今天则重置每日赠送并记一条流水。
    必须在调用方的事务内执行。"""
    cfg = get_config().credits
    grant = cfg.daily_grant
    today = today_key(now)
    row = conn.execute(
        "SELECT balance, daily_balance, daily_date FROM credit_accounts WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    if row is None:
        # 首次建账：注册赠送 + 今日赠送。注册赠送按 (signup_bonus, user, user_id) 幂等，
        # 所以积分上线前就存在的老用户第一次被读到时也会拿到同一笔赠送。
        bonus = cfg.signup_bonus
        conn.execute(
            "INSERT INTO credit_accounts (user_id, balance, daily_balance, daily_date, updated_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (user_id, bonus, grant, today, _now_iso()),
        )
        _insert_ledger(conn, user_id, bonus, "balance", bonus, KIND_SIGNUP_BONUS, ref_type="user", ref_id=user_id, note="注册赠送")
        _insert_ledger(conn, user_id, grant, "daily", grant, KIND_DAILY_GRANT, ref_type="day", ref_id=f"{user_id}:{today}")
        return Account(user_id, bonus, grant, today, grant)
    balance, daily_balance, daily_date = int(row["balance"]), int(row["daily_balance"]), row["daily_date"]
    if daily_date != today:
        daily_balance = grant
        conn.execute(
            "UPDATE credit_accounts SET daily_balance = ?, daily_date = ?, updated_at = ? WHERE user_id = ?",
            (grant, today, _now_iso(), user_id),
        )
        _insert_ledger(conn, user_id, grant, "daily", grant, KIND_DAILY_GRANT, ref_type="day", ref_id=f"{user_id}:{today}")
    return Account(user_id, balance, daily_balance, today, grant)


def _insert_ledger(
    conn: sqlite3.Connection,
    user_id: str,
    delta: int,
    bucket: str,
    balance_after: int,
    kind: str,
    *,
    action: str | None = None,
    ref_type: str | None = None,
    ref_id: str | None = None,
    note: str | None = None,
) -> bool:
    """返回 False 表示该 (kind, ref, bucket) 已存在（幂等命中），未写入。"""
    try:
        conn.execute(
            "INSERT INTO credit_ledger (user_id, delta, bucket, balance_after, kind, action,"
            " ref_type, ref_id, note, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (user_id, delta, bucket, balance_after, kind, action, ref_type, ref_id, note, _now_iso()),
        )
        return True
    except sqlite3.IntegrityError:
        return False


def get_account(user_id: str) -> Account:
    storage.init_db()
    with storage.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        return _load_account(conn, user_id)


# ---- spend / refund ---------------------------------------------------------


def charge(
    user_id: str,
    cost: int,
    *,
    action: str,
    ref_type: str,
    ref_id: str,
    note: str | None = None,
) -> Receipt:
    """原子扣费。余额不足抛 InsufficientCreditsError（402）；同一 ref 重复调用返回既有收据。"""
    storage.init_db()
    cost = max(0, int(cost))
    with storage.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        existing = conn.execute(
            "SELECT bucket, delta FROM credit_ledger WHERE kind = ? AND ref_type = ? AND ref_id = ?",
            (KIND_SPEND, ref_type, ref_id),
        ).fetchall()
        if existing:
            acct = _load_account(conn, user_id)
            from_daily = -sum(int(r["delta"]) for r in existing if r["bucket"] == "daily")
            from_balance = -sum(int(r["delta"]) for r in existing if r["bucket"] == "balance")
            return Receipt(from_daily + from_balance, from_daily, from_balance, acct.balance, acct.daily_balance, duplicate=True)

        acct = _load_account(conn, user_id)
        if cost == 0:
            return Receipt(0, 0, 0, acct.balance, acct.daily_balance)
        if acct.total < cost:
            raise InsufficientCreditsError({"required": cost, "available": acct.total, "action": action})

        from_daily = min(acct.daily_balance, cost)
        from_balance = cost - from_daily
        daily_after = acct.daily_balance - from_daily
        balance_after = acct.balance - from_balance
        conn.execute(
            "UPDATE credit_accounts SET balance = ?, daily_balance = ?, updated_at = ? WHERE user_id = ?",
            (balance_after, daily_after, _now_iso(), user_id),
        )
        if from_daily:
            _insert_ledger(conn, user_id, -from_daily, "daily", daily_after, KIND_SPEND,
                           action=action, ref_type=ref_type, ref_id=ref_id, note=note)
        if from_balance:
            _insert_ledger(conn, user_id, -from_balance, "balance", balance_after, KIND_SPEND,
                           action=action, ref_type=ref_type, ref_id=ref_id, note=note)
        return Receipt(cost, from_daily, from_balance, balance_after, daily_after)


def refund(user_id: str, *, ref_type: str, ref_id: str, note: str | None = None) -> int:
    """把某次扣费原路退回（管线失败时调用）。返回退回的积分数；无对应扣费或已退过返回 0。"""
    storage.init_db()
    with storage.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        spent = conn.execute(
            "SELECT bucket, delta, action FROM credit_ledger WHERE user_id = ? AND kind = ? AND ref_type = ? AND ref_id = ?",
            (user_id, KIND_SPEND, ref_type, ref_id),
        ).fetchall()
        if not spent:
            return 0
        acct = _load_account(conn, user_id)
        balance, daily = acct.balance, acct.daily_balance
        refunded = 0
        for r in spent:
            amount = -int(r["delta"])
            if r["bucket"] == "daily":
                daily += amount
                ok = _insert_ledger(conn, user_id, amount, "daily", daily, KIND_REFUND,
                                    action=r["action"], ref_type=ref_type, ref_id=ref_id, note=note)
                if not ok:
                    daily -= amount
                    continue
            else:
                balance += amount
                ok = _insert_ledger(conn, user_id, amount, "balance", balance, KIND_REFUND,
                                    action=r["action"], ref_type=ref_type, ref_id=ref_id, note=note)
                if not ok:
                    balance -= amount
                    continue
            refunded += amount
        if refunded:
            conn.execute(
                "UPDATE credit_accounts SET balance = ?, daily_balance = ?, updated_at = ? WHERE user_id = ?",
                (balance, daily, _now_iso(), user_id),
            )
        return refunded


# ---- grant ---------------------------------------------------------------------


def grant(
    user_id: str,
    amount: int,
    *,
    kind: str,
    ref_type: str | None = None,
    ref_id: str | None = None,
    note: str | None = None,
) -> Account:
    """向 balance 桶入账（可为负 = 管理员扣减，但不会扣成负数以下——下限 0）。
    带 ref 时幂等：同一 (kind, ref) 只入账一次。"""
    storage.init_db()
    with storage.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        acct = _load_account(conn, user_id)
        new_balance = max(0, acct.balance + int(amount))
        applied = new_balance - acct.balance
        if applied == 0 and amount != 0 and ref_id is None:
            return acct
        ok = _insert_ledger(conn, user_id, applied, "balance", new_balance, kind,
                            ref_type=ref_type, ref_id=ref_id, note=note)
        if not ok:
            return acct  # 幂等命中：同一 ref 已入账
        conn.execute(
            "UPDATE credit_accounts SET balance = ?, updated_at = ? WHERE user_id = ?",
            (new_balance, _now_iso(), user_id),
        )
        return Account(user_id, new_balance, acct.daily_balance, acct.daily_date, acct.daily_grant)


def grant_signup_bonus(user_id: str) -> Account:
    bonus = get_config().credits.signup_bonus
    return grant(user_id, bonus, kind=KIND_SIGNUP_BONUS, ref_type="user", ref_id=user_id, note="注册赠送")


# ---- reads ----------------------------------------------------------------------


def list_ledger(user_id: str, *, limit: int = 50, offset: int = 0) -> tuple[list[dict], int]:
    storage.init_db()
    with storage.connect() as conn:
        total = conn.execute("SELECT COUNT(*) FROM credit_ledger WHERE user_id = ?", (user_id,)).fetchone()[0]
        rows = conn.execute(
            "SELECT id, delta, bucket, balance_after, kind, action, ref_type, ref_id, note, created_at"
            " FROM credit_ledger WHERE user_id = ? ORDER BY id DESC LIMIT ? OFFSET ?",
            (user_id, limit, offset),
        ).fetchall()
    return [dict(r) for r in rows], int(total)


def spent_total(user_id: str) -> int:
    """累计消费（spend 减去 refund 的净值）。"""
    storage.init_db()
    with storage.connect() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(CASE WHEN kind = ? THEN -delta WHEN kind = ? THEN -delta ELSE 0 END), 0)"
            " FROM credit_ledger WHERE user_id = ?",
            (KIND_SPEND, KIND_REFUND, user_id),
        ).fetchone()
    return int(row[0])


def list_accounts(q: str = "", *, limit: int = 50, offset: int = 0) -> tuple[list[dict], int]:
    """管理后台：按用户名模糊搜索账户（含从未产生账户的用户，余额按 0 显示）。"""
    storage.init_db()
    like = f"%{q}%"
    with storage.connect() as conn:
        total = conn.execute("SELECT COUNT(*) FROM users WHERE username LIKE ?", (like,)).fetchone()[0]
        rows = conn.execute(
            """
            SELECT u.id AS user_id, u.username,
                   COALESCE(a.balance, 0) AS balance,
                   COALESCE(a.daily_balance, 0) AS daily_balance,
                   a.daily_date, a.updated_at
            FROM users u LEFT JOIN credit_accounts a ON a.user_id = u.id
            WHERE u.username LIKE ?
            ORDER BY a.updated_at DESC NULLS LAST, u.created_at DESC
            LIMIT ? OFFSET ?
            """,
            (like, limit, offset),
        ).fetchall()
    today = today_key()
    grant = get_config().credits.daily_grant
    items = []
    for r in rows:
        d = dict(r)
        # 惰性重置只在该用户下一次操作时落库；列表里按「今天会拿到的额度」显示
        if d["daily_date"] != today:
            d["daily_balance"] = grant
            d["daily_date"] = today
        items.append(d)
    return items, int(total)
