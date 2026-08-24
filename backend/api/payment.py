"""积分包购买（支付宝沙盒 / 离线 mock）—— 原独立服务 payment/ 的用户侧路由，2026-08 合并。

触碰支付宝 SDK（同步实现）的路由用 def，由 FastAPI 线程池执行，避免阻塞事件循环。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.deps import current_user
from backend.schemas import CreateOrderIn, OrderOut, PackOut, PaymentConfigOut, User
from backend.services.payment import orders as order_service
from backend.services.payment.packs import PACKS
from shared.config import get_config

router = APIRouter(prefix="/payment", tags=["payment"])


@router.get("/config", response_model=PaymentConfigOut)
def payment_config(_: User = Depends(current_user)) -> PaymentConfigOut:
    return PaymentConfigOut(mock_pay=get_config().payment.mock_pay)


@router.get("/packs", response_model=list[PackOut])
def list_packs(_: User = Depends(current_user)) -> list[PackOut]:
    return [PackOut(**vars(p)) for p in PACKS]


@router.post("/orders", response_model=OrderOut, status_code=201)
def create_order(body: CreateOrderIn, user: User = Depends(current_user)) -> dict:
    return order_service.create_order(user.id, body.pack_id, body.channel)


@router.get("/orders", response_model=list[OrderOut])
def my_orders(limit: int = 20, user: User = Depends(current_user)) -> list[dict]:
    return order_service.list_user_orders(user.id, limit=max(1, min(limit, 100)))


@router.get("/orders/{out_trade_no}", response_model=OrderOut)
def poll_order(out_trade_no: str, user: User = Depends(current_user)) -> dict:
    return order_service.sync_order_status(user.id, out_trade_no)


@router.post("/orders/{out_trade_no}/cancel", response_model=OrderOut)
def cancel_order(out_trade_no: str, user: User = Depends(current_user)) -> dict:
    return order_service.cancel_order(user.id, out_trade_no)


# 仅 PAYMENT_MOCK=true 时由 main.py 挂载：模拟买家完成支付
dev_router = APIRouter(prefix="/payment/dev", tags=["payment"])


@dev_router.post("/simulate-paid/{out_trade_no}", response_model=OrderOut)
def simulate_paid(out_trade_no: str, user: User = Depends(current_user)) -> dict:
    order = order_service.get_order(user.id, out_trade_no)
    order_service.mark_order_paid(order["out_trade_no"], alipay_trade_no="MOCK_TRADE")
    return order_service.get_order(user.id, out_trade_no)
