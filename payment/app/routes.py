from fastapi import APIRouter, Depends

from . import service
from .auth import AuthUser, get_current_user
from .config import get_settings
from .plans import PLANS
from .schemas import CreateOrderIn, HealthOut, MembershipOut, OrderOut, PlanOut

router = APIRouter(prefix="/payapi")

# 触碰支付宝 SDK(同步实现)的路由用 def,由 FastAPI 线程池执行,避免阻塞事件循环。


@router.get("/health", response_model=HealthOut)
def health() -> dict:
    return {"status": "ok", "mock_pay": get_settings().mock_pay}


@router.get("/plans", response_model=list[PlanOut])
def list_plans(_: AuthUser = Depends(get_current_user)) -> list:
    return [vars(plan) for plan in PLANS]


@router.get("/membership/me", response_model=MembershipOut)
def membership_me(user: AuthUser = Depends(get_current_user)) -> dict:
    return service.get_membership(user.id)


@router.post("/orders", response_model=OrderOut, status_code=201)
def create_order(body: CreateOrderIn, user: AuthUser = Depends(get_current_user)) -> dict:
    return service.create_order(user.id, body.plan_id, body.channel)


@router.get("/orders/{out_trade_no}", response_model=OrderOut)
def poll_order(out_trade_no: str, user: AuthUser = Depends(get_current_user)) -> dict:
    return service.sync_order_status(user.id, out_trade_no)


@router.post("/orders/{out_trade_no}/cancel", response_model=OrderOut)
def cancel_order(out_trade_no: str, user: AuthUser = Depends(get_current_user)) -> dict:
    return service.cancel_order(user.id, out_trade_no)


# 仅 MOCK_PAY=true 时由 main.py 挂载:模拟买家完成支付
dev_router = APIRouter(prefix="/payapi/dev")


@dev_router.post("/simulate-paid/{out_trade_no}", response_model=OrderOut)
def simulate_paid(out_trade_no: str, user: AuthUser = Depends(get_current_user)) -> dict:
    order = service.get_order(user.id, out_trade_no)
    service.mark_order_paid(order["out_trade_no"], alipay_trade_no="MOCK_TRADE")
    return service.get_order(user.id, out_trade_no)
