"""把账本接到各付费动作上的小工具（docs/credits-design.md §4）。

PaperCharge — 出卷 / 重新出卷的扣费器：价格取决于 Parser 解析出的
revision_intensity × total_questions，所以它作为 `on_request` 回调挂进
ai_engine.pipeline；回调里扣费，失败抛 InsufficientCreditsError 终止管线；
管线随后任何异常都由调用方 `refund()` 原路退回。

用法（backend/api/papers.py）：
    charge = PaperCharge(user.id)
    try:
        paper = ai_gateway.generate_paper(..., on_request=charge.on_request)
    except Exception:
        charge.refund()
        raise
    paper.metadata.update(charge.metadata())
"""
from __future__ import annotations

from uuid import uuid4

from backend.services.credits import ledger, pricing
from shared.schemas import GenerateRequest


class PaperCharge:
    def __init__(self, user_id: str, *, action: str | None = None, ref_type: str = "paper_gen", note: str | None = None):
        self.user_id = user_id
        self.action_override = action
        self.ref_type = ref_type
        self.ref_id = uuid4().hex
        self.note = note
        self.receipt: ledger.Receipt | None = None
        self.action: str | None = action

    def on_request(self, req: GenerateRequest) -> None:
        action = self.action_override or pricing.INTENSITY_ACTION.get(req.revision_intensity, "generate_fresh")
        cost = pricing.price(action, req.total_questions)
        self.action = action
        self.receipt = ledger.charge(
            self.user_id,
            cost,
            action=action,
            ref_type=self.ref_type,
            ref_id=self.ref_id,
            note=self.note or f"{pricing.PRICES[action].label} · {req.total_questions} 题",
        )

    def refund(self) -> int:
        if self.receipt is None or self.receipt.cost == 0:
            return 0
        return ledger.refund(self.user_id, ref_type=self.ref_type, ref_id=self.ref_id, note="出卷失败退回")

    def metadata(self) -> dict:
        """写进 Paper.metadata，前端据此刷新余额。"""
        if self.receipt is None:
            return {}
        return {
            "credits_charged": self.receipt.cost,
            "credits_action": self.action,
            "credits_balance_after": self.receipt.balance_after,
            "credits_daily_after": self.receipt.daily_after,
        }


def charge_request(user_id: str, req: GenerateRequest, *, ref_type: str, ref_id: str, note: str | None = None) -> ledger.Receipt:
    """对一个已经构造好的 GenerateRequest 直接扣费（学习计划按天出卷用）。"""
    action = pricing.INTENSITY_ACTION.get(req.revision_intensity, "generate_fresh")
    return ledger.charge(
        user_id,
        pricing.price(action, req.total_questions),
        action=action,
        ref_type=ref_type,
        ref_id=ref_id,
        note=note or f"{pricing.PRICES[action].label} · {req.total_questions} 题",
    )
