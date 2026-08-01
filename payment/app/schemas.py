from typing import Literal

from pydantic import BaseModel

OrderStatus = Literal["CREATED", "PAID", "EXPIRED", "CLOSED"]
# qr = 当面付扫码(需沙箱版支付宝 App);web = 电脑网站支付(桌面浏览器收银台)
PayChannel = Literal["qr", "web"]


class PlanOut(BaseModel):
    id: str
    name: str
    duration_days: int
    amount_cents: int
    description: str


class MembershipOut(BaseModel):
    user_id: str
    expires_at: str | None
    active: bool


class CreateOrderIn(BaseModel):
    plan_id: str
    channel: PayChannel = "qr"


class OrderOut(BaseModel):
    out_trade_no: str
    plan_id: str
    amount_cents: int
    status: OrderStatus
    channel: PayChannel
    qr_code: str | None
    pay_url: str | None
    created_at: str
    expires_at: str
    paid_at: str | None


class HealthOut(BaseModel):
    status: str
    mock_pay: bool


class GrantMembershipIn(BaseModel):
    days: int | None = None
    plan_id: str | None = None
