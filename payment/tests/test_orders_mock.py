from datetime import timedelta

import pytest

from app.config import format_iso, utcnow
from app.db import get_conn
from app.errors import PaymentError
from app import service

ENVELOPE_KEYS = {"error_code", "message", "detail", "trace_id"}


def test_full_mock_flow(client):
    assert client.get("/payapi/health").json() == {"status": "ok", "mock_pay": True}

    plans = client.get("/payapi/plans").json()
    assert [p["id"] for p in plans] == ["monthly", "quarterly", "yearly"]

    membership = client.get("/payapi/membership/me").json()
    assert membership == {"user_id": "dev-tester", "expires_at": None, "active": False}

    resp = client.post("/payapi/orders", json={"plan_id": "monthly"})
    assert resp.status_code == 201
    order = resp.json()
    assert order["status"] == "CREATED"
    assert order["qr_code"] == f"MOCK|{order['out_trade_no']}"

    otn = order["out_trade_no"]
    assert client.get(f"/payapi/orders/{otn}").json()["status"] == "CREATED"

    paid = client.post(f"/payapi/dev/simulate-paid/{otn}").json()
    assert paid["status"] == "PAID"
    assert paid["paid_at"] is not None

    membership = client.get("/payapi/membership/me").json()
    assert membership["active"] is True


def test_web_channel_order(client):
    resp = client.post("/payapi/orders", json={"plan_id": "monthly", "channel": "web"})
    assert resp.status_code == 201
    order = resp.json()
    assert order["channel"] == "web"
    assert order["qr_code"] is None
    assert order["pay_url"] is not None
    paid = client.post(f"/payapi/dev/simulate-paid/{order['out_trade_no']}").json()
    assert paid["status"] == "PAID"


def test_poll_expired_order(client):
    order = client.post("/payapi/orders", json={"plan_id": "monthly"}).json()
    stale = format_iso(utcnow() - timedelta(seconds=1))
    with get_conn() as conn:
        conn.execute(
            "UPDATE orders SET expires_at=? WHERE out_trade_no=?",
            (stale, order["out_trade_no"]),
        )
    polled = client.get(f"/payapi/orders/{order['out_trade_no']}").json()
    assert polled["status"] == "EXPIRED"
    # 过期单不能再被支付
    resp = client.post(f"/payapi/dev/simulate-paid/{order['out_trade_no']}")
    assert resp.json()["status"] == "EXPIRED"
    assert client.get("/payapi/membership/me").json()["active"] is False


def test_cancel_flow(client):
    order = client.post("/payapi/orders", json={"plan_id": "yearly"}).json()
    otn = order["out_trade_no"]
    assert client.post(f"/payapi/orders/{otn}/cancel").json()["status"] == "CLOSED"

    paid_order = client.post("/payapi/orders", json={"plan_id": "monthly"}).json()
    client.post(f"/payapi/dev/simulate-paid/{paid_order['out_trade_no']}")
    resp = client.post(f"/payapi/orders/{paid_order['out_trade_no']}/cancel")
    assert resp.status_code == 409
    body = resp.json()
    assert set(body) == ENVELOPE_KEYS
    assert body["error_code"] == "payment.order_not_cancelable"


def test_error_envelopes(client):
    resp = client.post("/payapi/orders", json={"plan_id": "nope"})
    assert resp.status_code == 404
    assert resp.json()["error_code"] == "payment.plan_not_found"

    resp = client.get("/payapi/orders/MJnotexist")
    assert resp.status_code == 404
    body = resp.json()
    assert set(body) == ENVELOPE_KEYS
    assert body["error_code"] == "payment.order_not_found"

    resp = client.post("/payapi/orders", json={})
    assert resp.status_code == 422
    assert resp.json()["error_code"] == "request.invalid"


def test_order_ownership(client, env):
    order = client.post("/payapi/orders", json={"plan_id": "monthly"}).json()
    # 其他用户访问同一订单 → 404,不泄露存在性
    with pytest.raises(PaymentError) as exc_info:
        service.get_order("someone-else", order["out_trade_no"])
    assert exc_info.value.error_code == "payment.order_not_found"
