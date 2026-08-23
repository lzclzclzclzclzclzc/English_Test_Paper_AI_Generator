"""积分账户（用户侧）：余额 / 价目表 / 流水。扣费本身发生在各付费端点里。"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.deps import current_user
from backend.schemas import (
    CreditAccountView,
    CreditLedgerItem,
    CreditLedgerList,
    CreditPriceItem,
    CreditPriceTable,
    User,
)
from backend.services import credits
from shared.config import get_config

router = APIRouter(prefix="/credits", tags=["credits"])


@router.get("/me", response_model=CreditAccountView)
def my_account(user: User = Depends(current_user)) -> CreditAccountView:
    acct = credits.get_account(user.id)
    return CreditAccountView(
        balance=acct.balance,
        daily_balance=acct.daily_balance,
        daily_grant=acct.daily_grant,
        total=acct.total,
        spent_total=credits.spent_total(user.id),
    )


@router.get("/prices", response_model=CreditPriceTable)
def prices(_: User = Depends(current_user)) -> CreditPriceTable:
    cfg = get_config().credits
    return CreditPriceTable(
        items=[CreditPriceItem(**p) for p in credits.price_table()],
        signup_bonus=cfg.signup_bonus,
        daily_grant=cfg.daily_grant,
    )


@router.get("/ledger", response_model=CreditLedgerList)
def ledger(limit: int = 50, offset: int = 0, user: User = Depends(current_user)) -> CreditLedgerList:
    limit = max(1, min(limit, 200))
    items, total = credits.list_ledger(user.id, limit=limit, offset=max(0, offset))
    return CreditLedgerList(items=[CreditLedgerItem(**i) for i in items], total=total)
