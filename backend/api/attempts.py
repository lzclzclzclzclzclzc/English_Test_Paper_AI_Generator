from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from backend.deps import current_user
from backend.errors import ResourceNotFoundError, ValidationError
from backend.services.grading import compare
from shared import storage
from shared.schemas import (
    Attempt,
    AttemptItem,
    GradeResultItem,
    GradeSubmissionItem,
    GradeSubmissionRequest,
    GradeSubmissionResponse,
    PaperItem,
    User,
)

router = APIRouter(prefix="/attempts", tags=["attempts"])


@router.post("", response_model=GradeSubmissionResponse)
async def submit_attempt(body: GradeSubmissionRequest, user: User = Depends(current_user)) -> GradeSubmissionResponse:
    paper = storage.get_paper(body.paper_id, user.id)
    if not paper:
        raise ResourceNotFoundError()
    by_index = _validate_submission_items(paper.items, body.items)
    results: list[GradeResultItem] = []
    attempt_items: list[AttemptItem] = []
    for submitted in body.items:
        paper_item = by_index[submitted.index]
        question = paper_item.question
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
            AttemptItem(
                source_question_id=paper_item.source_question_id,
                knowledge_point_ids=question.knowledge_point_ids,
                question_type=question.question_type,
                is_correct=is_correct,
            )
        )
    attempt = Attempt(user_id=user.id, paper_id=paper.paper_id, answered_at=datetime.now(timezone.utc), items=attempt_items)
    attempt_id = storage.write_attempt(attempt)
    storage.mark_paper_submitted(paper.paper_id)
    return GradeSubmissionResponse(attempt_id=attempt_id, items=results)


def _validate_submission_items(
    paper_items: list[PaperItem],
    submitted_items: list[GradeSubmissionItem],
) -> dict[int, PaperItem]:
    by_index = {item.index: item for item in paper_items}
    paper_indices = set(by_index)
    submitted_indices = [item.index for item in submitted_items]
    submitted_index_set = set(submitted_indices)
    duplicate_indices = sorted({index for index in submitted_indices if submitted_indices.count(index) > 1})
    unknown_indices = sorted(submitted_index_set - paper_indices)
    missing_indices = sorted(paper_indices - submitted_index_set)
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
