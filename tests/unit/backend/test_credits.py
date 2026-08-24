"""积分账本 + 积分包订单（docs/credits-design.md）单元测试。"""
from __future__ import annotations

import pytest

from backend.auth.password import hash_password
from backend.errors import InsufficientCreditsError, PaymentOrderNotCancelableError, PaymentPackNotFoundError
from backend.services import credits
from backend.services.payment import alipay_client
from backend.services.payment import orders as order_service
from shared import storage
from shared.config import reset_config_cache
from shared.schemas import GenerateRequest


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("BACKEND_ENV", "test")
    monkeypatch.setenv("PAYMENT_MOCK", "true")
    monkeypatch.setenv("CREDITS_SIGNUP_BONUS", "300")
    monkeypatch.setenv("CREDITS_DAILY_GRANT", "30")
    reset_config_cache()
    alipay_client.reset_pay_client()
    storage.set_db_path(tmp_path / "credits.db")
    storage.init_db()
    yield
    storage.set_db_path(None)
    alipay_client.reset_pay_client()
    reset_config_cache()


def _user(name="u1") -> str:
    storage.create_user(name, hash_password("secret1"))
    return storage.get_user_by_username(name).id


# ---- pricing ----


def test_price_table_shapes():
    assert credits.price("generate_original", 10) == 5 + 10 * 1
    assert credits.price("generate_light", 10) == 5 + 10 * 3
    assert credits.price("generate_fresh", 10) == 5 + 10 * 4
    assert credits.price("solution") == 5
    assert credits.price("writing_grade") == 20
    assert credits.price("agent_message") == 2
    assert credits.price("unknown_action", 99) == 0
    actions = {p["action"] for p in credits.price_table()}
    assert {"generate_original", "generate_light", "generate_fresh", "revise_paper", "solution", "writing_grade", "agent_message"} <= actions


# ---- account / daily grant ----


def test_account_lazy_create_with_signup_and_daily_grant(db):
    uid = _user()
    acct = credits.get_account(uid)
    assert acct.balance == 300 and acct.daily_balance == 30 and acct.total == 330
    # 再读不重复发
    again = credits.get_account(uid)
    assert again.balance == 300 and again.daily_balance == 30
    rows, total = credits.list_ledger(uid)
    assert total == 2 and {r["kind"] for r in rows} == {"signup_bonus", "daily_grant"}


def test_daily_grant_resets_next_day(db):
    uid = _user()
    credits.charge(uid, 20, action="solution", ref_type="t", ref_id="a")
    assert credits.get_account(uid).daily_balance == 10
    # 把 daily_date 拨回昨天 → 下一次读取重置为满额
    with storage.connect() as conn:
        conn.execute("UPDATE credit_accounts SET daily_date = '2000-01-01' WHERE user_id = ?", (uid,))
    assert credits.get_account(uid).daily_balance == 30


def test_signup_bonus_idempotent(db):
    uid = _user()
    a = credits.grant_signup_bonus(uid)
    b = credits.grant_signup_bonus(uid)
    assert a.balance == 300 and b.balance == 300
    rows, _ = credits.list_ledger(uid)
    assert sum(1 for r in rows if r["kind"] == "signup_bonus") == 1


# ---- charge / refund ----


def test_charge_spends_daily_first_then_balance(db):
    uid = _user()
    credits.grant_signup_bonus(uid)  # balance 300 + daily 30
    r = credits.charge(uid, 45, action="generate_light", ref_type="paper_gen", ref_id="p1")
    assert (r.from_daily, r.from_balance) == (30, 15)
    assert (r.daily_after, r.balance_after) == (0, 285)
    assert credits.get_account(uid).total == 285


def test_charge_insufficient_raises_402_with_detail(db):
    uid = _user()  # signup 300 + daily 30
    with pytest.raises(InsufficientCreditsError) as ei:
        credits.charge(uid, 331, action="generate_fresh", ref_type="paper_gen", ref_id="p2")
    assert ei.value.http_status == 402
    assert ei.value.detail == {"required": 331, "available": 330, "action": "generate_fresh"}
    # 失败不扣
    assert credits.get_account(uid).total == 330


def test_charge_is_idempotent_per_ref(db):
    uid = _user()
    credits.grant_signup_bonus(uid)
    r1 = credits.charge(uid, 50, action="solution", ref_type="x", ref_id="same")
    r2 = credits.charge(uid, 50, action="solution", ref_type="x", ref_id="same")
    assert r1.duplicate is False and r2.duplicate is True
    assert credits.get_account(uid).total == 330 - 50


def test_refund_returns_to_original_buckets_once(db):
    uid = _user()
    credits.grant_signup_bonus(uid)
    credits.charge(uid, 45, action="generate_light", ref_type="paper_gen", ref_id="p3")
    assert credits.refund(uid, ref_type="paper_gen", ref_id="p3") == 45
    acct = credits.get_account(uid)
    assert (acct.daily_balance, acct.balance) == (30, 300)
    # 重复退款无效
    assert credits.refund(uid, ref_type="paper_gen", ref_id="p3") == 0
    assert credits.refund(uid, ref_type="paper_gen", ref_id="never") == 0
    assert credits.spent_total(uid) == 0


def test_admin_grant_floor_zero(db):
    uid = _user()
    credits.grant(uid, 100, kind=credits.KIND_ADMIN_ADJUST, note="a")
    acct = credits.grant(uid, -5000, kind=credits.KIND_ADMIN_ADJUST, note="b")
    assert acct.balance == 0


def test_paper_charge_helper_prices_by_intensity(db):
    uid = _user()
    credits.grant_signup_bonus(uid)
    charge = credits.PaperCharge(uid)
    charge.on_request(GenerateRequest(total_questions=10, revision_intensity="fresh"))
    assert charge.receipt.cost == 45
    meta = charge.metadata()
    assert meta["credits_charged"] == 45 and meta["credits_action"] == "generate_fresh"
    assert charge.refund() == 45


# ---- orders ----


def test_order_flow_mock_pay_grants_credits_once(db):
    uid = _user()
    order = order_service.create_order(uid, "starter", "qr")
    assert order["status"] == "CREATED" and order["qr_code"].startswith("MOCK|") and order["credits"] == 1000
    # 轮询：mock 客户端永远 WAIT → 仍 CREATED
    assert order_service.sync_order_status(uid, order["out_trade_no"])["status"] == "CREATED"
    assert order_service.mark_order_paid(order["out_trade_no"], "T1") is True
    assert order_service.mark_order_paid(order["out_trade_no"], "T1") is False  # CAS 只赢一次
    acct = credits.get_account(uid)
    assert acct.balance == 300 + 1000
    rows, _ = credits.list_ledger(uid)
    assert sum(1 for r in rows if r["kind"] == "purchase") == 1
    # 对账：无缺口
    assert order_service.reconcile_paid_orders() == 0
    # 已支付不可取消
    with pytest.raises(PaymentOrderNotCancelableError):
        order_service.cancel_order(uid, order["out_trade_no"])


def test_order_web_channel_cancel_and_expire(db, monkeypatch):
    uid = _user()
    order = order_service.create_order(uid, "standard", "web")
    assert order["pay_url"].startswith("MOCK|") and order["qr_code"] is None
    cancelled = order_service.cancel_order(uid, order["out_trade_no"])
    assert cancelled["status"] == "CLOSED"

    order2 = order_service.create_order(uid, "annual", "qr")
    with storage.connect() as conn:
        conn.execute("UPDATE orders SET expires_at = '2000-01-01T00:00:00Z' WHERE out_trade_no = ?", (order2["out_trade_no"],))
    assert order_service.sync_order_status(uid, order2["out_trade_no"])["status"] == "EXPIRED"
    assert credits.get_account(uid).balance == 300  # 只有注册赠送，没入账


def test_order_unknown_pack_and_ownership(db):
    uid = _user("a")
    other = _user("b")
    with pytest.raises(PaymentPackNotFoundError):
        order_service.create_order(uid, "platinum")
    order = order_service.create_order(uid, "starter")
    from backend.errors import PaymentOrderNotFoundError

    with pytest.raises(PaymentOrderNotFoundError):
        order_service.get_order(other, order["out_trade_no"])


def test_reconcile_fills_missing_purchase(db):
    uid = _user()
    order = order_service.create_order(uid, "starter")
    # 模拟 CAS 成功但入账前崩溃：直接把订单标 PAID
    with storage.connect() as conn:
        conn.execute("UPDATE orders SET status='PAID', paid_at='2026-08-23T00:00:00Z' WHERE out_trade_no=?", (order["out_trade_no"],))
    assert order_service.reconcile_paid_orders() == 1
    assert credits.get_account(uid).balance == 300 + 1000
    assert order_service.reconcile_paid_orders() == 0
