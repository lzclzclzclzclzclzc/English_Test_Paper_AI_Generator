from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from backend.deps import current_user
from backend.errors import ResourceNotFoundError, ValidationError
from backend.schemas import (
    GradeResultItem,
    GradeSubmissionItem,
    GradeSubmissionRequest,
    GradeSubmissionResponse,
    StoredAttempt,
    StoredAttemptItem,
    User,
)
from backend.services.grading import compare
from shared import storage
from shared.schemas import PaperItem
from backend.schemas import WritingGradeResultItem

router = APIRouter(prefix="/attempts", tags=["attempts"])


@router.post("", response_model=GradeSubmissionResponse)
async def submit_attempt(body: GradeSubmissionRequest, user: User = Depends(current_user)) -> GradeSubmissionResponse:
    paper = storage.get_paper(body.paper_id, user.id)
    if not paper:
        raise ResourceNotFoundError()
    by_index = _validate_submission_items(paper.items, body.items)
    results: list[GradeResultItem] = []
    attempt_items: list[StoredAttemptItem] = []
    for submitted in body.items:
        paper_item = by_index[submitted.index]
        question = paper_item.question
        # Skip writing questions — graded via /api/writing/grade, not here.
        if question.question_type == "writing":
            continue
        is_correct = compare(submitted.user_answer, question.answer, question.question_type)
        results.append(
            GradeResultItem(
                index=submitted.index,
                user_answer=submitted.user_answer,
                correct_answer=question.answer,
                is_correct=is_correct,
            )
        )
        attempt_items.append(
            StoredAttemptItem(
                index=paper_item.index,
                source_question_id=paper_item.source_question_id,
                knowledge_point_ids=question.knowledge_point_ids,
                question_type=question.question_type,
                is_correct=is_correct,
                user_answer=submitted.user_answer,
            )
        )
    attempt = StoredAttempt(user_id=user.id, paper_id=paper.paper_id, answered_at=datetime.now(timezone.utc), items=attempt_items)
    attempt_id = storage.write_attempt_and_mark_paper_submitted(attempt)
    return GradeSubmissionResponse(attempt_id=attempt_id, items=results)


def _validate_submission_items(
    paper_items: list[PaperItem],
    submitted_items: list[GradeSubmissionItem],
) -> dict[int, PaperItem]:
    by_index = {item.index: item for item in paper_items}
    # Writing questions are graded separately via /api/writing/grade — they are
    # NOT required in this submission. Only non-writing indices must be covered.
    required_indices = {
        item.index for item in paper_items if item.question.question_type != "writing"
    }
    submitted_indices = [item.index for item in submitted_items]
    submitted_index_set = set(submitted_indices)
    duplicate_indices = sorted({index for index in submitted_indices if submitted_indices.count(index) > 1})
    unknown_indices = sorted(submitted_index_set - set(by_index))
    missing_indices = sorted(required_indices - submitted_index_set)
    if duplicate_indices or unknown_indices or missing_indices:
        raise ValidationError(
            {
                "items": {
                    "duplicate_indices": duplicate_indices,
                    "unknown_indices": unknown_indices,
                    "missing_indices": missing_indices,
                }
            }
        )
    return by_index


@router.get("/by-paper/{paper_id}", response_model=GradeSubmissionResponse | None)
async def get_attempt_by_paper(
    paper_id: str,
    user: User = Depends(current_user),
) -> GradeSubmissionResponse | None:
    """Return the latest attempt result for a paper (for review replay), or
    null if never submitted. correct_answer is reconstructed from the paper."""
    attempt = storage.get_latest_attempt(paper_id, user.id)
    if not attempt:
        return None
    paper = storage.get_paper(paper_id, user.id)
    if not paper:
        raise ResourceNotFoundError()
    answer_by_index = {item.index: item.question.answer for item in paper.items}
    items = [
        GradeResultItem(
            index=it["index"],
            user_answer=it["user_answer"] if it["user_answer"] is not None else "",
            correct_answer=answer_by_index.get(it["index"], ""),
            is_correct=it["is_correct"],
        )
        for it in attempt["items"]
    ]
    return GradeSubmissionResponse(attempt_id=attempt["attempt_id"], items=items)
