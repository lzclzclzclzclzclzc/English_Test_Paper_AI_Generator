from dataclasses import dataclass

from .errors import PaymentError


@dataclass(frozen=True)
class Plan:
    id: str
    name: str
    duration_days: int
    amount_cents: int
    description: str


PLANS: list[Plan] = [
    Plan("monthly", "月度会员", 30, 990, "30 天全部功能"),
    Plan("quarterly", "季度会员", 90, 2500, "90 天全部功能"),
    Plan("yearly", "年度会员", 365, 8800, "365 天全部功能"),
]


def get_plan(plan_id: str) -> Plan:
    for plan in PLANS:
        if plan.id == plan_id:
            return plan
    raise PaymentError(404, "payment.plan_not_found", f"套餐不存在:{plan_id}")
