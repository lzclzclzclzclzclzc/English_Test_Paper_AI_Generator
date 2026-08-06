"""Writing grading endpoint.

Separate from objective question grading (POST /api/attempts). Essay grading
requires LLM-based multi-dimensional scoring (content/language/organization)
which takes 5-15 seconds, so we isolate it in its own endpoint.
"""
from __future__ import annotations

import httpx

from fastapi import APIRouter, Depends, HTTPException

from pydantic import BaseModel

from backend.deps import current_user, rate_limiter
from backend.schemas import (
    User,
    WritingGradeRequest,
    WritingGradeResponse,
    WritingGradeResultItem,
)
from backend.services import ai_gateway
from shared.config import get_config
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


def _check_membership_via_payment_service(user_id: str) -> bool:
    """Call payment service to check membership status.

    Semantics mirror the frontend `useMembership` hook:
    - 200 with active=true  → member (return True)
    - 200 with active=false → non-member (return False)
    - Network error / 401 / other unexpected status → payment service is
      considered not enabled, so we treat the user as "not locked" and hence
      a member for detail-display purposes. This matches the frontend rule
      `locked = query.isSuccess && !isMember` where failure keeps locked=false.
    """
    config = get_config()
    payment_url = config.backend.payment_service_url
    try:
        resp = httpx.get(
            f"{payment_url}/payapi/membership/me",
            headers={"X-User-Id": user_id},
            timeout=3.0,
        )
        if resp.status_code == 200:
            data = resp.json()
            return bool(data.get("active", False))
        # 4xx/5xx other than 200: treat as service unavailable → unlocked
        return True
    except Exception:
        return True


@router.post("/grade", response_model=WritingGradeResponse)
async def grade_writing(
    body: WritingGradeRequest,
    user: User = Depends(rate_limiter("writing", "rate_limit_writing_per_min")),
) -> WritingGradeResponse:
    """Grade one or more essay submissions.

    Returns structured multi-dimensional scoring results. Detailed analysis
    (content_analysis, language_analysis, etc.) is included for all users;
    the backend does NOT strip them — the frontend conditionally displays
    based on membership status.

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

    # Check membership status once for all essays
    is_member = _check_membership_via_payment_service(user.id)

    results: list[WritingGradeResultItem] = []
    save_items: list[dict] = []
    attempt_write_items: list[dict] = []
    for item in body.items:
        paper_item = idx_to_item.get(item.index)
        if not paper_item:
            continue
        q = paper_item.question
        if q.question_type != "writing":
            continue

        # Grade the essay
        grade_result = ai_gateway.grade_writing(q, item.user_essay)

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

        # Detailed analysis fields are stored in full; response is gated by membership.
        result = WritingGradeResultItem(
            index=item.index,
            total_score=grade_result.total_score,
            content_score=grade_result.content_score,
            language_score=grade_result.language_score,
            organization_score=grade_result.organization_score,
            word_count=grade_result.word_count,
            level=grade_result.level,
            content_analysis=grade_result.content_analysis if is_member else None,
            language_analysis=grade_result.language_analysis if is_member else None,
            organization_analysis=grade_result.organization_analysis if is_member else None,
            overall_comment=grade_result.overall_comment if is_member else None,
            revised_version=grade_result.revised_version if is_member else None,
        )
        results.append(result)

    # Persist full essay content + grade + analysis for history replay
    if save_items:
        storage.save_writing_grade_results(user.id, body.paper_id, save_items)
        storage.save_writing_attempt_items(user.id, body.paper_id, attempt_write_items)
        # Ensure paper is marked submitted so list-views reflect "已提交"
        storage.mark_paper_submitted_if_needed(body.paper_id, user.id)

    return WritingGradeResponse(paper_id=body.paper_id, results=results)


@router.get("/by-paper/{paper_id}", response_model=StoredWritingGradeHistoryResponse | None)
async def get_writing_grades(
    paper_id: str,
    user: User = Depends(current_user),
) -> StoredWritingGradeHistoryResponse | None:
    """Return saved history writing grades for a paper.

    Membership gating mirrors POST /grade — non-members do not see
    content_analysis/language_analysis/organization_analysis/overall_comment/
    revised_version but still get the essay text and scores.
    """
    paper = storage.get_paper(paper_id, user.id)
    if not paper:
        raise HTTPException(status_code=404, detail="paper not found")
    rows = storage.get_writing_grade_results(paper_id, user.id)
    if not rows:
        return None
    is_member = _check_membership_via_payment_service(user.id)
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
                content_analysis=r.get("content_analysis") if is_member else None,
                language_analysis=r.get("language_analysis") if is_member else None,
                organization_analysis=r.get("organization_analysis") if is_member else None,
                overall_comment=r.get("overall_comment") if is_member else None,
                revised_version=r.get("revised_version") if is_member else None,
            ),
        )
    return StoredWritingGradeHistoryResponse(paper_id=paper_id, results=results)