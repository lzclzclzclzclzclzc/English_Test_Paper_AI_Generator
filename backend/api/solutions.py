from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.deps import rate_limiter
from backend.schemas import CreditChargeInfo, SolutionRequest, SolutionResponse, User
from backend.services import ai_gateway, credits

router = APIRouter(prefix="/solutions", tags=["solutions"])


@router.post("", response_model=SolutionResponse)
async def generate_solution(
    body: SolutionRequest,
    user: User = Depends(rate_limiter("solutions", "rate_limit_solutions_per_min")),
) -> SolutionResponse:
    # 积分：每次讲解都打一次 LLM，先扣后算；LLM 失败自动退回（charged 上下文）。
    with credits.charged(
        user.id, credits.price("solution"), action="solution",
        ref_type="solution", note=f"AI 讲解 · {body.source_question_id or '题目'}",
        refund_note="讲解失败退回",
    ) as receipt:
        solution = ai_gateway.generate_solution(
            body.question,
            source_question_id=body.source_question_id,
            revision_mode=body.revision_mode,
            user_answer=body.user_answer,
        )
    return SolutionResponse(
        solution=solution,
        credits=CreditChargeInfo(cost=receipt.cost, balance_after=receipt.balance_after, daily_after=receipt.daily_after),
    )
