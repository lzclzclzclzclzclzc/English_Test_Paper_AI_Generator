from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.deps import current_user
from backend.schemas import User
from shared import storage
from shared.schemas import KnowledgePoint

router = APIRouter(prefix="/knowledge-points", tags=["knowledge-points"])


@router.get("", response_model=list[KnowledgePoint])
async def list_knowledge_points(_: User = Depends(current_user)) -> list[KnowledgePoint]:
    """Full KP catalog (id / level1 / level2 中文名) for frontend display."""
    return storage.list_knowledge_points()
