from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends

from backend.deps import current_user
from backend.errors import ResourceNotFoundError, ValidationError
from backend.schemas import (
    CreditChargeInfo,
    User,
    VocabularyExampleRequest,
    VocabularyExampleResponse,
    VocabularyJudgmentRequest,
    VocabularyJudgmentResponse,
    VocabularyProgressResponse,
    VocabularySettingsRequest,
    VocabularySettingsResponse,
    VocabularyTodayResponse,
)
from backend.services import ai_gateway, credits
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
    return VocabularySettingsResponse(**storage.set_vocabulary_daily_new_limit(user.id, body.daily_new_limit))


@router.post("/example", response_model=VocabularyExampleResponse)
async def generate_example(
    body: VocabularyExampleRequest, user: User = Depends(current_user),
) -> VocabularyExampleResponse:
    """按需为单词生成一个 AI 例句（消耗 1 积分，与 /solutions 同一套先扣后算、失败退回）。"""
    word = storage.get_vocabulary_word(body.word_id)
    if word is None:
        raise ResourceNotFoundError("单词不存在")

    ref_id = uuid4().hex
    receipt = credits.charge(
        user.id, credits.price("vocab_example"), action="vocab_example",
        ref_type="vocab_example", ref_id=ref_id, note=f"AI 例句 · {word['term']}",
    )
    try:
        example_en, example_zh = ai_gateway.generate_vocabulary_example(
            word["term"], word["part_of_speech"], word["meanings"],
        )
    except Exception:
        credits.refund(user.id, ref_type="vocab_example", ref_id=ref_id, note="例句生成失败退回")
        raise
    return VocabularyExampleResponse(
        word_id=body.word_id,
        example_en=example_en,
        example_zh=example_zh,
        credits=CreditChargeInfo(
            cost=receipt.cost, balance_after=receipt.balance_after, daily_after=receipt.daily_after,
        ),
    )
