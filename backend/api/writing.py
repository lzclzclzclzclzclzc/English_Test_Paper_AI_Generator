"""Writing grading endpoint.

Separate from objective question grading (POST /api/attempts). Essay grading
requires LLM-based multi-dimensional scoring (content/language/organization)
which takes 5-15 seconds, so we isolate it in its own endpoint.
"""
from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException

from pydantic import BaseModel

from backend.deps import current_user, rate_limiter
from backend.schemas import (
    CreditChargeInfo,
    User,
    WritingGradeRequest,
    WritingGradeResponse,
    WritingGradeResultItem,
)
from backend.services import ai_gateway, credits
from shared import storage

router = APIRouter(prefix="/writing", tags=["writing"])


class StoredWritingGradeHistoryItem(BaseModel):
    index: int
    user_essay: str
    total_score: float
    content_score: float
    language_score: float
    organization_score: float
    word_count: int
    level: str
    content_analysis: str | None = None
    language_analysis: str | None = None
    organization_analysis: str | None = None
    overall_comment: str | None = None
    revised_version: str | None = None


class StoredWritingGradeHistoryResponse(BaseModel):
    paper_id: str
    results: list[StoredWritingGradeHistoryItem]


@router.post("/grade", response_model=WritingGradeResponse)
async def grade_writing(
    body: WritingGradeRequest,
    user: User = Depends(rate_limiter("writing", "rate_limit_writing_per_min")),
) -> WritingGradeResponse:
    """Grade one or more essay submissions.

    Returns structured multi-dimensional scoring results with full detailed
    analysis. 每篇作文按价目表扣积分（writing_grade），LLM 失败时原路退回。

    Args:
        body: paper_id + list of {index, user_essay}
        user: authenticated user (rate-limited)

    Returns:
        WritingGradeResponse with per-essay results
    """
    paper = storage.get_paper(body.paper_id, user.id)
    if not paper:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="paper not found")
    
    # Build index -> paper item map (need source_question_id for attempt_items)
    idx_to_item = {item.index: item for item in paper.items}

    # 只对真正会被批改的作文计费：先筛出有效条目，按篇数一次性扣费
    to_grade = [
        (item, idx_to_item[item.index])
        for item in body.items
        if item.index in idx_to_item and idx_to_item[item.index].question.question_type == "writing"
    ]
    charge_ref = uuid4().hex
    receipt = credits.charge(
        user.id,
        credits.price("writing_grade") * len(to_grade),
        action="writing_grade",
        ref_type="writing_grade",
        ref_id=charge_ref,
        note=f"作文批改 {len(to_grade)} 篇 · paper {body.paper_id[:8]}",
    )

    results: list[WritingGradeResultItem] = []
    save_items: list[dict] = []
    attempt_write_items: list[dict] = []
    for item, paper_item in to_grade:
        q = paper_item.question

        # Grade the essay（LLM 失败 → 退回本次全部扣费再抛出）
        try:
            grade_result = ai_gateway.grade_writing(q, item.user_essay)
        except Exception:
            credits.refund(user.id, ref_type="writing_grade", ref_id=charge_ref, note="批改失败退回")
            raise

        save_items.append(
            {
                "index": item.index,
                "user_essay": item.user_essay,
                "total_score": grade_result.total_score,
                "content_score": grade_result.content_score,
                "language_score": grade_result.language_score,
                "organization_score": grade_result.organization_score,
                "word_count": grade_result.word_count,
                "level": grade_result.level,
                "content_analysis": grade_result.content_analysis,
                "language_analysis": grade_result.language_analysis,
                "organization_analysis": grade_result.organization_analysis,
                "overall_comment": grade_result.overall_comment,
                "revised_version": grade_result.revised_version,
            },
        )
        attempt_write_items.append(
            {
                "index": item.index,
                "source_question_id": paper_item.source_question_id,
                "knowledge_point_ids": q.knowledge_point_ids,
                "user_essay": item.user_essay,
            },
        )

        result = WritingGradeResultItem(
            index=item.index,
            total_score=grade_result.total_score,
            content_score=grade_result.content_score,
            language_score=grade_result.language_score,
            organization_score=grade_result.organization_score,
            word_count=grade_result.word_count,
            level=grade_result.level,
            content_analysis=grade_result.content_analysis,
            language_analysis=grade_result.language_analysis,
            organization_analysis=grade_result.organization_analysis,
            overall_comment=grade_result.overall_comment,
            revised_version=grade_result.revised_version,
        )
        results.append(result)

    # Persist full essay content + grade + analysis for history replay
    if save_items:
        storage.save_writing_grade_results(user.id, body.paper_id, save_items)
        storage.save_writing_attempt_items(user.id, body.paper_id, attempt_write_items)
        # Ensure paper is marked submitted so list-views reflect "已提交"
        storage.mark_paper_submitted_if_needed(body.paper_id, user.id)

    return WritingGradeResponse(
        paper_id=body.paper_id,
        results=results,
        credits=CreditChargeInfo(cost=receipt.cost, balance_after=receipt.balance_after, daily_after=receipt.daily_after),
    )


@router.get("/by-paper/{paper_id}", response_model=StoredWritingGradeHistoryResponse | None)
async def get_writing_grades(
    paper_id: str,
    user: User = Depends(current_user),
) -> StoredWritingGradeHistoryResponse | None:
    """Return saved history writing grades for a paper.

    Full detail for everyone (detail gating ended with the 2026-08 credits switch).
    """
    paper = storage.get_paper(paper_id, user.id)
    if not paper:
        raise HTTPException(status_code=404, detail="paper not found")
    rows = storage.get_writing_grade_results(paper_id, user.id)
    if not rows:
        return None
    results: list[StoredWritingGradeHistoryItem] = []
    for r in rows:
        results.append(
            StoredWritingGradeHistoryItem(
                index=r["item_index"],
                user_essay=r["user_essay"],
                total_score=float(r["total_score"]),
                content_score=float(r["content_score"]),
                language_score=float(r["language_score"]),
                organization_score=float(r["organization_score"]),
                word_count=int(r["word_count"]),
                level=r["level"],
                content_analysis=r.get("content_analysis"),
                language_analysis=r.get("language_analysis"),
                organization_analysis=r.get("organization_analysis"),
                overall_comment=r.get("overall_comment"),
                revised_version=r.get("revised_version"),
            ),
        )
    return StoredWritingGradeHistoryResponse(paper_id=paper_id, results=results)