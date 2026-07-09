from __future__ import annotations

from fastapi import APIRouter, Depends

import ai_engine
from backend.deps import rate_limiter
from shared.schemas import SolutionRequest, SolutionResponse, User

router = APIRouter(prefix="/solutions", tags=["solutions"])


@router.post("", response_model=SolutionResponse)
async def generate_solution(
    body: SolutionRequest,
    user: User = Depends(rate_limiter("solutions", "rate_limit_solutions_per_min")),
) -> SolutionResponse:
    solution = ai_engine.generate_solution(
        body.question,
        source_question_id=body.source_question_id,
        revision_mode=body.revision_mode,
    )
    return SolutionResponse(solution=solution)
