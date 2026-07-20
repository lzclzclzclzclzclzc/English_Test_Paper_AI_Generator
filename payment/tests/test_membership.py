from datetime import timedelta

from app.config import format_iso, parse_iso, utcnow
from app.db import get_conn
from app import service

USER = "u1"


def _paid_expiry(user_id: str) -> str:
    return service.get_membership(user_id)["expires_at"]


def _buy(user_id: str, plan_id: str) -> dict:
    order = service.create_order(user_id, plan_id)
    service.mark_order_paid(order["out_trade_no"])
    return service.get_order(user_id, order["out_trade_no"])


def test_first_purchase_extends_from_now(env):
    before = utcnow()
    _buy(USER, "monthly")
    expiry = parse_iso(_paid_expiry(USER))
    # format_iso 截断微秒,下界放宽 2 秒
    assert timedelta(days=30) - timedelta(seconds=2) <= expiry - before <= timedelta(days=30, minutes=1)


def test_active_membership_extends_from_current_expiry(env):
    _buy(USER, "monthly")
    first = parse_iso(_paid_expiry(USER))
    _buy(USER, "quarterly")
    second = parse_iso(_paid_expiry(USER))
    assert second == first + timedelta(days=90)


def test_lapsed_membership_extends_from_now(env):
    _buy(USER, "monthly")
    lapsed = format_iso(utcnow() - timedelta(days=10))
    with get_conn() as conn:
        conn.execute("UPDATE memberships SET expires_at=? WHERE user_id=?", (lapsed, USER))
    before = utcnow()
    _buy(USER, "monthly")
    expiry = parse_iso(_paid_expiry(USER))
    # 从 now 顺延,而不是从已过期的旧到期日
    assert timedelta(days=30) - timedelta(seconds=2) <= expiry - before <= timedelta(days=30, minutes=1)


def test_double_mark_paid_extends_once(env):
    order = service.create_order(USER, "monthly")
    service.mark_order_paid(order["out_trade_no"])
    first = _paid_expiry(USER)
    service.mark_order_paid(order["out_trade_no"])  # 重复通知
    assert _paid_expiry(USER) == first


def test_membership_active_flag(env):
    assert service.get_membership(USER) == {
        "user_id": USER,
        "expires_at": None,
        "active": False,
    }
    _buy(USER, "monthly")
    assert service.get_membership(USER)["active"] is True
    lapsed = format_iso(utcnow() - timedelta(seconds=5))
    with get_conn() as conn:
        conn.execute("UPDATE memberships SET expires_at=? WHERE user_id=?", (lapsed, USER))
    assert service.get_membership(USER)["active"] is False
