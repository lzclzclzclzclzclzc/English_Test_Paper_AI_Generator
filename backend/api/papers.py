from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.deps import current_user, rate_limiter
from backend.errors import ResourceNotFoundError
from backend.schemas import GeneratePaperRequest, PaperListResponse, RevisePaperRequest, User
from backend.services import ai_gateway
from shared import storage
from shared.schemas import Paper

router = APIRouter(prefix="/papers", tags=["papers"])


@router.post("/generate", response_model=Paper)
async def generate_paper(
    body: GeneratePaperRequest,
    user: User = Depends(rate_limiter("generate", "rate_limit_generate_per_min")),
) -> Paper:
    paper = ai_gateway.generate_paper(
        user_query=body.user_query,
        mode=body.mode,
        wrong_items=body.wrong_items,
        user_id=user.id,
        review_window_days=body.review_window_days,
    )
    storage.save_paper(paper, user.id)
    return paper


@router.post("/revise", response_model=Paper)
async def revise_paper(body: RevisePaperRequest, user: User = Depends(current_user)) -> Paper:
    current = storage.get_paper(body.paper_id, user.id)
    if not current:
        raise ResourceNotFoundError()
    paper = ai_gateway.revise_paper(current, body.user_instruction)
    storage.save_paper(paper, user.id)
    return paper


@router.get("", response_model=PaperListResponse)
async def list_papers(
    user: User = Depends(current_user),
    limit: int = 100,
    offset: int = 0,
    submitted: bool | None = None,
    question_type: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> PaperListResponse:
    return PaperListResponse(items=storage.list_papers(
        user.id, limit=limit, offset=offset,
        submitted=submitted, question_type=question_type,
        start_date=start_date, end_date=end_date))


@router.get("/{paper_id}", response_model=Paper)
async def get_paper(paper_id: str, user: User = Depends(current_user)) -> Paper:
    paper = storage.get_paper(paper_id, user.id)
    if not paper:
        raise ResourceNotFoundError()
    return paper
