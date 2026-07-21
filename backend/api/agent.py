from __future__ import annotations

import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend.deps import current_user
from backend.schemas import AgentChatRequest, AgentChatResponse, User
from shared import storage

router = APIRouter(prefix="/agent", tags=["agent"])

_PAPER_RE = re.compile(r'<paper_ready\s+paper_id="([^"]+)"\s*/>')


def _parse_action(reply: str) -> dict | None:
    m = _PAPER_RE.search(reply)
    if m:
        return {"type": "open_paper", "paper_id": m.group(1)}
    return None


def _ensure_agent_path() -> None:
    project_root = Path(__file__).parent.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))


@router.post("/chat", response_model=AgentChatResponse)
async def agent_chat(
    body: AgentChatRequest,
    user: User = Depends(current_user),
) -> AgentChatResponse:
    _ensure_agent_path()
    from agents import Runner
    from agent.coach import create_coach_agent

    agent = create_coach_agent()
    system_ctx = {"role": "system", "content": f"当前用户ID：{user.id}，用户名：{user.username}"}
    full_input = [system_ctx] + body.history + [{"role": "user", "content": body.message}]

    result = await Runner.run(agent, input=full_input)
    reply: str = result.final_output or ""
    history = list(result.to_input_list())
    action = _parse_action(reply)

    return AgentChatResponse(reply=reply, history=history, action=action)


# ─── Extract Plan ──────────────────────────────────────────────────────────

class ExtractPlanRequest(BaseModel):
    plan_text: str = Field(min_length=1)
    start_date: str | None = None   # YYYY-MM-DD; defaults to today


class StudyPlanDayOut(BaseModel):
    index: int
    date: str | None
    knowledge_point_id: str
    kp_name: str
    question_type: str
    count: int
    note: str
    paper_id: str
    paper_title: str


class StudyPlanOut(BaseModel):
    plan_id: str
    user_id: str
    total_days: int
    created_at: str
    days: list[StudyPlanDayOut]


@router.post("/extract-plan", response_model=StudyPlanOut)
async def extract_plan(
    body: ExtractPlanRequest,
    user: User = Depends(current_user),
) -> StudyPlanOut:
    """Phase 2: extract structured plan from natural-language text, generate
    one paper per day, persist and return the study plan."""
    _ensure_agent_path()
    from agent.plan_extractor import extract_study_plan
    from ai_engine import retriever as _retriever
    from ai_engine import reviser as _reviser

    start = date.fromisoformat(body.start_date) if body.start_date else date.today()

    plan_data = extract_study_plan(body.plan_text, user_id=user.id, start_date=start)

    days_out: list[StudyPlanDayOut] = []
    for day in plan_data.days:
        from shared.schemas import GenerateRequest
        req = GenerateRequest(
            total_questions=day.count,
            knowledge_points=[day.knowledge_point_id],
            question_types=[day.question_type],
            revision_intensity="light",
            user_id=user.id,
        )
        retrieval = _retriever.retrieve(req)
        paper = _reviser.build_paper(req, retrieval)
        storage.save_paper(paper, user.id)

        day_date = None
        if body.start_date:
            from datetime import timedelta
            d = start + timedelta(days=day.index - 1)
            day_date = d.isoformat()

        days_out.append(StudyPlanDayOut(
            index=day.index,
            date=day_date,
            knowledge_point_id=day.knowledge_point_id,
            kp_name=day.kp_name,
            question_type=day.question_type,
            count=day.count,
            note=day.note,
            paper_id=paper.paper_id,
            paper_title=paper.title,
        ))

    serialisable = {
        "total_days": plan_data.total_days,
        "days": [d.model_dump() for d in days_out],
    }
    plan_id = storage.save_study_plan(user.id, plan_data.total_days, serialisable)

    return StudyPlanOut(
        plan_id=plan_id,
        user_id=user.id,
        total_days=plan_data.total_days,
        created_at=datetime.now(timezone.utc).isoformat(),
        days=days_out,
    )


@router.get("/study-plans/latest", response_model=StudyPlanOut | None)
async def get_latest_study_plan(user: User = Depends(current_user)) -> StudyPlanOut | None:
    """Return the user's latest active study plan, or null if none exists."""
    plan = storage.get_latest_study_plan(user.id)
    if not plan:
        return None
    days = [StudyPlanDayOut(**d) for d in plan["days"]]
    return StudyPlanOut(
        plan_id="",
        user_id=user.id,
        total_days=plan["total_days"],
        created_at="",
        days=days,
    )
