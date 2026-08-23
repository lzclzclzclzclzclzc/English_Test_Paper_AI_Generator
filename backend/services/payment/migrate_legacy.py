"""一次性迁移：旧独立支付服务 payment/data/payment.db → 主库（docs/credits-design.md §6）。

- orders：原样导入（plan_id → pack_id 映射 monthly→starter / quarterly→standard /
  yearly→annual，credits 按新包面值），已存在的 out_trade_no 跳过。**不**为历史
  PAID 订单补发积分（当时买的是会员时长，已按下面规则折算）。
- memberships：仍在有效期内的会员，把剩余天数按 `LEGACY_PLAN_CREDITS_PER_DAY`
  （1000 积分 / 30 天）折成积分一次性入账（kind=migrate_membership，按 user_id 幂等）。
- 旧库里 `dev-` 前缀的假用户（PAYMENT_DEV_FAKE_USER）在主库不存在，直接跳过。
"""
from __future__ import annotations

import math
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from backend.services import credits
from shared import storage

_PLAN_TO_PACK = {"monthly": "starter", "quarterly": "standard", "yearly": "annual"}
_PACK_CREDITS = {"starter": 1000, "standard": 3000, "annual": 12000}
_CREDITS_PER_DAY = 1000 / 30


def _parse_iso(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def migrate_payment_db(src: Path) -> dict:
    src = Path(src)
    if not src.is_file():
        return {"error": f"源库不存在: {src}"}
    storage.init_db()
    legacy = sqlite3.connect(src)
    legacy.row_factory = sqlite3.Row
    try:
        tables = {r["name"] for r in legacy.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        orders = list(legacy.execute("SELECT * FROM orders")) if "orders" in tables else []
        members = list(legacy.execute("SELECT * FROM memberships")) if "memberships" in tables else []
    finally:
        legacy.close()

    with storage.connect() as conn:
        known_users = {r["id"] for r in conn.execute("SELECT id FROM users")}
        existing = {r["out_trade_no"] for r in conn.execute("SELECT out_trade_no FROM orders")}

    imported = skipped_orders = 0
    with storage.connect() as conn:
        for o in orders:
            if o["out_trade_no"] in existing or o["user_id"] not in known_users:
                skipped_orders += 1
                continue
            pack_id = _PLAN_TO_PACK.get(o["plan_id"], o["plan_id"])
            cols = o.keys()
            conn.execute(
                "INSERT INTO orders(out_trade_no, user_id, pack_id, amount_cents, credits, status, channel,"
                " qr_code, pay_url, alipay_trade_no, created_at, expires_at, paid_at)"
                " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    o["out_trade_no"], o["user_id"], pack_id, o["amount_cents"], _PACK_CREDITS.get(pack_id, 0),
                    o["status"], o["channel"] if "channel" in cols else "qr",
                    o["qr_code"], o["pay_url"] if "pay_url" in cols else None, o["alipay_trade_no"],
                    o["created_at"], o["expires_at"], o["paid_at"],
                ),
            )
            # 历史 PAID 订单已兑现为会员时长，下面按剩余天数折算；这里写一条 0 积分的 purchase
            # 流水占住幂等位，避免 reconcile-orders 再次补发。
            if o["status"] == "PAID":
                credits.grant(o["user_id"], 0, kind=credits.KIND_PURCHASE, ref_type="order",
                              ref_id=o["out_trade_no"], note=f"历史会员订单 {o['plan_id']}（已按剩余天数折算）")
            imported += 1

    now = datetime.now(timezone.utc)
    converted = []
    for m in members:
        if m["user_id"] not in known_users:
            continue
        remaining = (_parse_iso(m["expires_at"]) - now).total_seconds() / 86400
        if remaining <= 0:
            continue
        amount = int(math.ceil(remaining * _CREDITS_PER_DAY))
        credits.grant(m["user_id"], amount, kind=credits.KIND_MIGRATE_MEMBERSHIP, ref_type="user",
                      ref_id=m["user_id"], note=f"会员剩余 {remaining:.1f} 天折算")
        converted.append({"user_id": m["user_id"], "days": round(remaining, 1), "credits": amount})

    return {
        "orders_imported": imported,
        "orders_skipped": skipped_orders,
        "memberships_converted": converted,
    }
