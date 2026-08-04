from fastapi import APIRouter, Depends

from . import service
from .auth import AuthUser, require_admin
from .plans import get_plan
from .schemas import GrantMembershipIn

admin_router = APIRouter(prefix="/payapi/admin")


@admin_router.get("/memberships")
def list_memberships(q: str = "", limit: int = 50, offset: int = 0, _: AuthUser = Depends(require_admin)) -> dict:
    return {"items": service.list_memberships(q, limit, offset), "total": service.count_memberships(q)}


@admin_router.get("/memberships/{user_id}")
def membership_detail(user_id: str, _: AuthUser = Depends(require_admin)) -> dict:
    return service.get_membership(user_id)


@admin_router.post("/memberships/{user_id}/grant")
def grant(user_id: str, body: GrantMembershipIn, _: AuthUser = Depends(require_admin)) -> dict:
    days = body.days if body.days is not None else get_plan(body.plan_id).duration_days
    service.extend_membership(user_id, days)
    return service.get_membership(user_id)


@admin_router.post("/memberships/{user_id}/revoke")
def revoke(user_id: str, _: AuthUser = Depends(require_admin)) -> dict:
    return service.revoke_membership(user_id)


@admin_router.get("/orders")
def list_orders(status: str | None = None, limit: int = 50, offset: int = 0, _: AuthUser = Depends(require_admin)) -> dict:
    return {"items": service.list_orders(status, limit, offset)}
