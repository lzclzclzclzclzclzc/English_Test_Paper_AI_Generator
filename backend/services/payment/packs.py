"""积分包（原 payment/app/plans.py 的会员套餐，2026-08 改为一次性购买积分）。

1 积分 ≈ ¥0.01；大包多送。硬编码与原实现一致——改价只改这里，
`GET /api/payment/packs` 原样下发给前端。
"""
from __future__ import annotations

from dataclasses import dataclass

from backend.errors import PaymentPackNotFoundError


@dataclass(frozen=True)
class Pack:
    id: str
    name: str
    credits: int
    amount_cents: int
    description: str


PACKS: list[Pack] = [
    Pack("starter", "入门包", 1000, 990, "1000 积分 · 约 20 张改编卷"),
    Pack("standard", "标准包", 3000, 2500, "3000 积分 · 比入门包多送 20%"),
    Pack("annual", "畅练包", 12000, 8800, "12000 积分 · 比入门包多送 35%"),
]


def get_pack(pack_id: str) -> Pack:
    for pack in PACKS:
        if pack.id == pack_id:
            return pack
    raise PaymentPackNotFoundError(f"pack not found: {pack_id}")


# 旧会员套餐 → 迁移换算（backend.cli migrate-payment-db）：按天折算成积分
LEGACY_PLAN_CREDITS_PER_DAY = {
    "monthly": 1000 / 30,
    "quarterly": 3000 / 90,
    "yearly": 12000 / 365,
}
