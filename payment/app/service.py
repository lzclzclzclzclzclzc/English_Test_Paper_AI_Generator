import secrets
import string
from datetime import timedelta

from .alipay_client import get_pay_client
from .config import format_iso, get_settings, parse_iso, utcnow, utcnow_iso
from .db import get_conn
from .errors import PaymentError
from .plans import get_plan

_ALNUM = string.ascii_lowercase + string.digits


def _new_out_trade_no() -> str:
    stamp = utcnow().strftime("%Y%m%d%H%M%S")
    rand = "".join(secrets.choice(_ALNUM) for _ in range(6))
    return f"MJ{stamp}{rand}"


def _row_to_order(row) -> dict:
    return dict(row)


def create_order(user_id: str, plan_id: str, channel: str = "qr") -> dict:
    plan = get_plan(plan_id)
    out_trade_no = _new_out_trade_no()
    subject = f"墨卷会员·{plan.name}"
    client = get_pay_client()
    if channel == "web":
        qr_code = None
        pay_url = client.page_pay_url(out_trade_no, plan.amount_cents, subject)
    else:
        qr_code = client.precreate(out_trade_no, plan.amount_cents, subject)
        pay_url = None
    now = utcnow()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO orders(out_trade_no, user_id, plan_id, amount_cents, status,"
            " channel, qr_code, pay_url, created_at, expires_at)"
            " VALUES(?,?,?,?, 'CREATED', ?,?,?,?,?)",
            (
                out_trade_no,
                user_id,
                plan.id,
                plan.amount_cents,
                channel,
                qr_code,
                pay_url,
                format_iso(now),
                format_iso(now + timedelta(seconds=get_settings().order_ttl_seconds)),
            ),
        )
    return get_order(user_id, out_trade_no)


def get_order(user_id: str, out_trade_no: str) -> dict:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM orders WHERE out_trade_no=? AND user_id=?",
            (out_trade_no, user_id),
        ).fetchone()
    if row is None:
        raise PaymentError(404, "payment.order_not_found", "订单不存在")
    return _row_to_order(row)


def sync_order_status(user_id: str, out_trade_no: str) -> dict:
    """轮询入口:惰性过期 + 向支付宝查单同步状态。"""
    order = get_order(user_id, out_trade_no)
    if order["status"] != "CREATED":
        return order

    if utcnow_iso() > order["expires_at"]:
        with get_conn() as conn:
            conn.execute(
                "UPDATE orders SET status='EXPIRED'"
                " WHERE out_trade_no=? AND status='CREATED'",
                (out_trade_no,),
            )
        return get_order(user_id, out_trade_no)

    result = get_pay_client().query(out_trade_no)
    if result.paid:
        mark_order_paid(out_trade_no, alipay_trade_no=result.trade_no)
    elif result.closed:
        with get_conn() as conn:
            conn.execute(
                "UPDATE orders SET status='CLOSED'"
                " WHERE out_trade_no=? AND status='CREATED'",
                (out_trade_no,),
            )
    return get_order(user_id, out_trade_no)


def mark_order_paid(out_trade_no: str, alipay_trade_no: str | None = None) -> None:
    """标记支付成功并顺延会员,幂等:CAS 只允许 CREATED→PAID 成功一次,
    只有赢得这次转移的调用才执行会员顺延,重复通知不会重复加时长。"""
    now = utcnow()
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE orders SET status='PAID', paid_at=?, alipay_trade_no=?"
            " WHERE out_trade_no=? AND status='CREATED'",
            (format_iso(now), alipay_trade_no, out_trade_no),
        )
        if cur.rowcount != 1:
            return
        row = conn.execute(
            "SELECT user_id, plan_id FROM orders WHERE out_trade_no=?",
            (out_trade_no,),
        ).fetchone()
        plan = get_plan(row["plan_id"])
        current = conn.execute(
            "SELECT expires_at FROM memberships WHERE user_id=?",
            (row["user_id"],),
        ).fetchone()
        base = now
        if current is not None:
            base = max(parse_iso(current["expires_at"]), now)
        new_expiry = format_iso(base + timedelta(days=plan.duration_days))
        conn.execute(
            "INSERT INTO memberships(user_id, expires_at, updated_at) VALUES(?,?,?)"
            " ON CONFLICT(user_id) DO UPDATE SET"
            " expires_at=excluded.expires_at, updated_at=excluded.updated_at",
            (row["user_id"], new_expiry, format_iso(now)),
        )


def cancel_order(user_id: str, out_trade_no: str) -> dict:
    order = get_order(user_id, out_trade_no)
    if order["status"] == "PAID":
        raise PaymentError(409, "payment.order_not_cancelable", "订单已支付,无法取消")
    with get_conn() as conn:
        conn.execute(
            "UPDATE orders SET status='CLOSED'"
            " WHERE out_trade_no=? AND status='CREATED'",
            (out_trade_no,),
        )
    return get_order(user_id, out_trade_no)


def get_membership(user_id: str) -> dict:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT expires_at FROM memberships WHERE user_id=?", (user_id,)
        ).fetchone()
    if row is None:
        return {"user_id": user_id, "expires_at": None, "active": False}
    expires_at = row["expires_at"]
    return {
        "user_id": user_id,
        "expires_at": expires_at,
        "active": expires_at > utcnow_iso(),
    }


def list_memberships(q: str = "", limit: int = 50, offset: int = 0) -> list[dict]:
    return []


def count_memberships(q: str = "") -> int:
    return 0
