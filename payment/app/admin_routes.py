from fastapi import APIRouter, Depends

from . import service
from .auth import AuthUser, require_admin

admin_router = APIRouter(prefix="/payapi/admin")


@admin_router.get("/memberships")
def list_memberships(q: str = "", limit: int = 50, offset: int = 0, _: AuthUser = Depends(require_admin)) -> dict:
    return {"items": service.list_memberships(q, limit, offset), "total": service.count_memberships(q)}
