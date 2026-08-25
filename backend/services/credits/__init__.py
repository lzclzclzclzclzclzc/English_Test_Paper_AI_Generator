"""积分系统：价目表（pricing）+ 账本（ledger）。

用法：
    from backend.services import credits
    cost = credits.price("generate_light", units=10)
    receipt = credits.charge(user_id, cost, action="generate_light", ref_type="paper", ref_id=paper_id)
    ...  # 失败时 credits.refund(user_id, ref_type="paper", ref_id=paper_id)
"""
from backend.services.credits.ledger import (  # noqa: F401
    KIND_ADMIN_ADJUST,
    KIND_DAILY_GRANT,
    KIND_MIGRATE_MEMBERSHIP,
    KIND_PURCHASE,
    KIND_REFUND,
    KIND_SIGNUP_BONUS,
    KIND_SPEND,
    Account,
    Receipt,
    charge,
    get_account,
    grant,
    grant_signup_bonus,
    list_accounts,
    list_ledger,
    refund,
    spent_total,
    today_key,
)
from backend.services.credits.charging import PaperCharge, charge_request, charged  # noqa: F401
from backend.services.credits.pricing import INTENSITY_ACTION, PRICES, price, price_table  # noqa: F401
