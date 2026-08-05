from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.deps import current_user
from backend.errors import ValidationError
from backend.schemas import (
    User,
    VocabularyJudgmentRequest,
    VocabularyJudgmentResponse,
    VocabularyProgressResponse,
    VocabularySettingsRequest,
    VocabularySettingsResponse,
    VocabularyTodayResponse,
)
from shared import storage

router = APIRouter(prefix="/vocabulary", tags=["vocabulary"])


@router.get("/today", response_model=VocabularyTodayResponse)
async def today(user: User = Depends(current_user)) -> VocabularyTodayResponse:
    return VocabularyTodayResponse(**storage.get_vocabulary_today(user.id))


@router.post("/judgments", response_model=VocabularyJudgmentResponse)
async def judge(body: VocabularyJudgmentRequest, user: User = Depends(current_user)) -> VocabularyJudgmentResponse:
    try:
        return VocabularyJudgmentResponse(**storage.judge_vocabulary_card(user.id, body.word_id, body.rating))
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc


@router.get("/progress", response_model=VocabularyProgressResponse)
async def progress(user: User = Depends(current_user)) -> VocabularyProgressResponse:
    return VocabularyProgressResponse(**storage.get_vocabulary_progress(user.id))


@router.patch("/settings", response_model=VocabularySettingsResponse)
async def settings(body: VocabularySettingsRequest, user: User = Depends(current_user)) -> VocabularySettingsResponse:
    return VocabularySettingsResponse(daily_new_limit=storage.set_vocabulary_daily_new_limit(user.id, body.daily_new_limit))
