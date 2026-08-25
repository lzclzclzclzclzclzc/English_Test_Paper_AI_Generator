"""积分包订单（原 payment/app/service.py，2026-08 合并进主后端）。

- 订单状态机 `CREATED → PAID | EXPIRED | CLOSED`；二维码有效期 order_ttl_seconds，
  过期在轮询时惰性判定，无后台任务。
- 支付成功用单事务 CAS（`UPDATE ... WHERE status='CREATED'`）保证 CREATED→PAID
  只发生一次；只有赢得转移的调用才给积分入账，且入账本身又靠账本的唯一 ref
  （purchase / order / out_trade_no）二次幂等。
- 存储在主库 `orders` 表（shared/storage.py MIGRATION_CREDITS_AND_ORDERS）。
"""
from __future__ import annotations

import secrets
import string
from datetime import datetime, timedelta, timezone

from backend.errors import PaymentOrderNotCancelableError, PaymentOrderNotFoundError
from backend.services import credits
from backend.services.payment.alipay_client import get_pay_client
from backend.services.payment.packs import get_pack
from shared import storage
from shared.config import get_config

_ALNUM = string.ascii_lowercase + string.digits


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def format_iso(dt: datetime) -> str:
    """统一为秒精度的 ...Z 格式,保证同格式字符串可直接按字典序比较。"""
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def utcnow_iso() -> str:
    return format_iso(utcnow())


def _new_out_trade_no() -> str:
    stamp = utcnow().strftime("%Y%m%d%H%M%S")
    rand = "".join(secrets.choice(_ALNUM) for _ in range(6))
    return f"JW{stamp}{rand}"


def create_order(user_id: str, pack_id: str, channel: str = "qr") -> dict:
    pack = get_pack(pack_id)
    out_trade_no = _new_out_trade_no()
    subject = f"卷王积分·{pack.name}"
    client = get_pay_client()
    if channel == "web":
        qr_code = None
        pay_url = client.page_pay_url(out_trade_no, pack.amount_cents, subject)
    else:
        qr_code = client.precreate(out_trade_no, pack.amount_cents, subject)
        pay_url = None
    now = utcnow()
    storage.init_db()
    with storage.connect() as conn:
        conn.execute(
            "INSERT INTO orders(out_trade_no, user_id, pack_id, amount_cents, credits, status,"
            " channel, qr_code, pay_url, created_at, expires_at)"
            " VALUES(?,?,?,?,?, 'CREATED', ?,?,?,?,?)",
            (
                out_trade_no,
                user_id,
                pack.id,
                pack.amount_cents,
                pack.credits,
                channel,
                qr_code,
                pay_url,
                format_iso(now),
                format_iso(now + timedelta(seconds=get_config().payment.order_ttl_seconds)),
            ),
        )
    return get_order(user_id, out_trade_no)


def get_order(user_id: str, out_trade_no: str) -> dict:
    storage.init_db()
    with storage.connect() as conn:
        row = conn.execute(
            "SELECT * FROM orders WHERE out_trade_no=? AND user_id=?",
            (out_trade_no, user_id),
        ).fetchone()
    if row is None:
        raise PaymentOrderNotFoundError(out_trade_no)
    return dict(row)


def sync_order_status(user_id: str, out_trade_no: str) -> dict:
    """轮询入口:惰性过期 + 向支付宝查单同步状态。"""
    order = get_order(user_id, out_trade_no)
    if order["status"] != "CREATED":
        return order

    if utcnow_iso() > order["expires_at"]:
        with storage.connect() as conn:
            conn.execute(
                "UPDATE orders SET status='EXPIRED' WHERE out_trade_no=? AND status='CREATED'",
                (out_trade_no,),
            )
        return get_order(user_id, out_trade_no)

    result = get_pay_client().query(out_trade_no)
    if result.paid:
        mark_order_paid(out_trade_no, alipay_trade_no=result.trade_no)
    elif result.closed:
        with storage.connect() as conn:
            conn.execute(
                "UPDATE orders SET status='CLOSED' WHERE out_trade_no=? AND status='CREATED'",
                (out_trade_no,),
            )
    return get_order(user_id, out_trade_no)


def mark_order_paid(out_trade_no: str, alipay_trade_no: str | None = None) -> bool:
    """标记支付成功并给积分入账。幂等:CAS 只允许 CREATED→PAID 成功一次,
    只有赢得这次转移的调用才入账;入账再由账本的唯一 ref 兜底。返回是否为本次赢得转移。"""
    now = utcnow()
    storage.init_db()
    with storage.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        cur = conn.execute(
            "UPDATE orders SET status='PAID', paid_at=?, alipay_trade_no=?"
            " WHERE out_trade_no=? AND status='CREATED'",
            (format_iso(now), alipay_trade_no, out_trade_no),
        )
        if cur.rowcount != 1:
            return False
        row = conn.execute(
            "SELECT user_id, pack_id, credits FROM orders WHERE out_trade_no=?",
            (out_trade_no,),
        ).fetchone()
        user_id, pack_id, amount = row["user_id"], row["pack_id"], int(row["credits"])
    # 入账走 credits.grant（自己的 BEGIN IMMEDIATE 事务 + 唯一 ref 幂等）。
    # 两段之间进程崩溃的极端情况由 reconcile_paid_orders() 补账。
    credits.grant(
        user_id,
        amount,
        kind=credits.KIND_PURCHASE,
        ref_type="order",
        ref_id=out_trade_no,
        note=f"购买积分包 {pack_id}",
    )
    return True


def reconcile_paid_orders() -> int:
    """对账:PAID 订单若没有对应 purchase 流水则补入账。返回补账单数。"""
    storage.init_db()
    with storage.connect() as conn:
        rows = conn.execute(
            """
            SELECT o.out_trade_no, o.user_id, o.pack_id, o.credits
            FROM orders o
            LEFT JOIN credit_ledger l
              ON l.kind = 'purchase' AND l.ref_type = 'order' AND l.ref_id = o.out_trade_no
            WHERE o.status = 'PAID' AND l.id IS NULL
            """
        ).fetchall()
    for r in rows:
        credits.grant(
            r["user_id"], int(r["credits"]), kind=credits.KIND_PURCHASE,
            ref_type="order", ref_id=r["out_trade_no"], note=f"购买积分包 {r['pack_id']}（对账补入）",
        )
    return len(rows)


def cancel_order(user_id: str, out_trade_no: str) -> dict:
    order = get_order(user_id, out_trade_no)
    if order["status"] == "PAID":
        raise PaymentOrderNotCancelableError(out_trade_no)
    with storage.connect() as conn:
        conn.execute(
            "UPDATE orders SET status='CLOSED' WHERE out_trade_no=? AND status='CREATED'",
            (out_trade_no,),
        )
    return get_order(user_id, out_trade_no)


def list_orders(
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
    *,
    out_trade_no: str = "",
    user_q: str = "",
    pack_id: str = "",
    created_from: str = "",
    created_to: str = "",
    paid_from: str = "",
    paid_to: str = "",
) -> tuple[list[dict], int]:
    """Admin order listing with header-column filters. `user_q` matches either
    the order's user_id or the buyer's username (both live in app.db, so the
    subquery JOIN is intra-database). Date filters compare the YYYY-MM-DD prefix
    of the ISO timestamps; a paid-date filter naturally excludes unpaid rows."""
    storage.init_db()
    clauses: list[str] = []
    params: list[object] = []
    if status:
        clauses.append("status = ?")
        params.append(status)
    if out_trade_no:
        clauses.append("out_trade_no LIKE ?")
        params.append(f"%{out_trade_no}%")
    if user_q:
        clauses.append("(user_id LIKE ? OR user_id IN (SELECT id FROM users WHERE username LIKE ?))")
        params += [f"%{user_q}%", f"%{user_q}%"]
    if pack_id:
        clauses.append("pack_id = ?")
        params.append(pack_id)
    if created_from:
        clauses.append("substr(created_at, 1, 10) >= ?")
        params.append(created_from)
    if created_to:
        clauses.append("substr(created_at, 1, 10) <= ?")
        params.append(created_to)
    if paid_from:
        clauses.append("substr(paid_at, 1, 10) >= ?")
        params.append(paid_from)
    if paid_to:
        clauses.append("substr(paid_at, 1, 10) <= ?")
        params.append(paid_to)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with storage.connect() as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM orders {where}", params).fetchone()[0]
        rows = conn.execute(
            f"SELECT * FROM orders {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (*params, limit, offset),
        ).fetchall()
    return [dict(r) for r in rows], int(total)


def list_user_orders(user_id: str, limit: int = 20) -> list[dict]:
    storage.init_db()
    with storage.connect() as conn:
        rows = conn.execute(
            "SELECT * FROM orders WHERE user_id=? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def revenue_stats(days: int = 30) -> dict:
    """PAID-only revenue aggregates for the admin dashboard.

    total_cents is all-history; revenue_by_day / by_pack cover the last
    `days` days (by paid_at)."""
    since = format_iso(utcnow() - timedelta(days=days))
    storage.init_db()
    with storage.connect() as conn:
        total_cents = conn.execute(
            "SELECT COALESCE(SUM(amount_cents), 0) FROM orders WHERE status='PAID'"
        ).fetchone()[0]
        by_day = [
            {"day": r["day"], "cents": r["cents"]}
            for r in conn.execute(
                "SELECT substr(paid_at, 1, 10) AS day, SUM(amount_cents) AS cents"
                " FROM orders WHERE status='PAID' AND paid_at >= ?"
                " GROUP BY day ORDER BY day",
                (since,),
            )
        ]
        by_pack = [
            {"pack_id": r["pack_id"], "orders": r["orders"], "cents": r["cents"]}
            for r in conn.execute(
                "SELECT pack_id, COUNT(*) AS orders, SUM(amount_cents) AS cents"
                " FROM orders WHERE status='PAID' AND paid_at >= ?"
                " GROUP BY pack_id ORDER BY cents DESC",
                (since,),
            )
        ]
    return {"total_cents": int(total_cents), "revenue_by_day": by_day, "by_pack": by_pack}


def paying_user_count() -> int:
    storage.init_db()
    with storage.connect() as conn:
        return int(conn.execute("SELECT COUNT(DISTINCT user_id) FROM orders WHERE status='PAID'").fetchone()[0])
