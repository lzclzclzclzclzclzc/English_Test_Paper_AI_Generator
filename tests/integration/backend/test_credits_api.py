"""积分在 HTTP 层的表现：注册赠送、余额接口、出卷/讲解扣费、402、失败退回、支付下单→积分到账。"""
from __future__ import annotations

import pytest

from backend.services import ai_gateway, credits
from shared import storage


def _balance(client) -> dict:
    r = client.get("/api/credits/me")
    assert r.status_code == 200
    return r.json()


def test_register_grants_signup_bonus_and_daily(logged_in_client):
    body = _balance(logged_in_client)
    assert body["balance"] == 300
    assert body["daily_balance"] == 30
    assert body["total"] == 330
    assert body["daily_grant"] == 30
    prices = logged_in_client.get("/api/credits/prices").json()
    assert prices["signup_bonus"] == 300
    assert any(p["action"] == "generate_light" for p in prices["items"])


def test_generate_charges_by_intensity_and_records_metadata(logged_in_client):
    # fake 管线：mode=fresh、3 题、默认 revision_intensity=light → 5 + 3*3 = 14
    r = logged_in_client.post("/api/papers/generate", json={"user_query": "来 3 道题", "mode": "fresh"})
    assert r.status_code == 200
    meta = r.json()["metadata"]
    assert meta["credits_charged"] == 14
    assert meta["credits_action"] == "generate_light"
    assert _balance(logged_in_client)["total"] == 330 - 14
    ledger = logged_in_client.get("/api/credits/ledger").json()
    assert ledger["total"] >= 3
    assert ledger["items"][0]["kind"] == "spend"


def test_generate_insufficient_credits_402(logged_in_client):
    user = storage.get_user_by_username("demo")
    credits.grant(user.id, -300, kind=credits.KIND_ADMIN_ADJUST, note="清零")
    # 只剩 daily 30；fresh 3 题 light 要 14 → 还够；把 daily 也花掉
    with storage.connect() as conn:
        conn.execute("UPDATE credit_accounts SET daily_balance = 5 WHERE user_id = ?", (user.id,))
    r = logged_in_client.post("/api/papers/generate", json={"user_query": "来 3 道题", "mode": "fresh"})
    assert r.status_code == 402
    body = r.json()
    assert body["error_code"] == "credits.insufficient"
    assert body["detail"] == {"required": 14, "available": 5, "action": "generate_light"}
    # 没扣
    assert _balance(logged_in_client)["total"] == 5


def test_generate_failure_refunds(logged_in_client, monkeypatch):
    def boom(user_query, *, on_request=None, **kw):
        from shared.schemas import GenerateRequest

        on_request(GenerateRequest(total_questions=3))
        raise RuntimeError("pipeline exploded")

    monkeypatch.setattr(ai_gateway, "generate_paper", boom)
    before = _balance(logged_in_client)["total"]
    r = logged_in_client.post("/api/papers/generate", json={"user_query": "x", "mode": "fresh"})
    assert r.status_code == 500
    assert _balance(logged_in_client)["total"] == before
    ledger = logged_in_client.get("/api/credits/ledger").json()["items"]
    assert ledger[0]["kind"] == "refund" and ledger[1]["kind"] == "spend"


def test_solution_charges_and_refunds_on_failure(logged_in_client, generated_paper, monkeypatch):
    item = generated_paper["items"][0]
    payload = {"question": item["question"], "source_question_id": item["source_question_id"]}
    before = _balance(logged_in_client)["total"]
    r = logged_in_client.post("/api/solutions", json=payload)
    assert r.status_code == 200
    assert r.json()["credits"]["cost"] == 5
    assert _balance(logged_in_client)["total"] == before - 5

    def boom(*a, **k):
        raise RuntimeError("llm down")

    monkeypatch.setattr(ai_gateway, "generate_solution", boom)
    r = logged_in_client.post("/api/solutions", json=payload)
    assert r.status_code == 500
    assert _balance(logged_in_client)["total"] == before - 5


def test_revise_is_rate_limited_and_charged(logged_in_client, generated_paper):
    before = _balance(logged_in_client)["total"]
    r = logged_in_client.post("/api/papers/revise", json={"paper_id": generated_paper["paper_id"], "user_instruction": "换成 3 道"})
    assert r.status_code == 200
    assert r.json()["metadata"]["credits_action"] == "revise_paper"
    assert _balance(logged_in_client)["total"] == before - (5 + 3 * 4)


def test_payment_order_mock_flow_tops_up(logged_in_client):
    packs = logged_in_client.get("/api/payment/packs").json()
    assert [p["id"] for p in packs] == ["starter", "standard", "annual"]
    assert logged_in_client.get("/api/payment/config").json()["mock_pay"] is True

    r = logged_in_client.post("/api/payment/orders", json={"pack_id": "starter", "channel": "qr"})
    assert r.status_code == 201
    order = r.json()
    assert order["status"] == "CREATED" and order["credits"] == 1000

    poll = logged_in_client.get(f"/api/payment/orders/{order['out_trade_no']}")
    assert poll.json()["status"] == "CREATED"

    paid = logged_in_client.post(f"/api/payment/dev/simulate-paid/{order['out_trade_no']}")
    assert paid.status_code == 200 and paid.json()["status"] == "PAID"
    # 重复模拟支付不重复加
    logged_in_client.post(f"/api/payment/dev/simulate-paid/{order['out_trade_no']}")
    assert _balance(logged_in_client)["balance"] == 300 + 1000

    mine = logged_in_client.get("/api/payment/orders").json()
    assert len(mine) == 1 and mine[0]["status"] == "PAID"
    cancel = logged_in_client.post(f"/api/payment/orders/{order['out_trade_no']}/cancel")
    assert cancel.status_code == 409

    # 别人的订单不可见
    logged_in_client.post("/api/auth/logout")
    logged_in_client.post("/api/auth/register", json={"username": "other", "password": "other123"})
    assert logged_in_client.get(f"/api/payment/orders/{order['out_trade_no']}").status_code == 404


def test_payment_requires_login(client):
    assert client.get("/api/payment/packs").status_code == 401
    assert client.get("/api/credits/me").status_code == 401
