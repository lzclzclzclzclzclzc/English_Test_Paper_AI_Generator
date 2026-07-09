from __future__ import annotations

from fastapi import APIRouter, Depends

import ai_engine
from backend.deps import current_user
from shared.schemas import MasteryProfile, User

router = APIRouter(prefix="/users/me", tags=["mastery"])


@router.get("/mastery", response_model=MasteryProfile)
async def mastery(window_days: int | None = None, user: User = Depends(current_user)) -> MasteryProfile:
    return ai_engine.build_profile(user.id, window_days)
