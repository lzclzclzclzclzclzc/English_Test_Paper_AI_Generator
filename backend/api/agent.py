from __future__ import annotations

import re
import sys
from pathlib import Path

from fastapi import APIRouter, Depends
from pydantic import BaseModel

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
    from agent.tools import set_current_user_id

    # Bind the authenticated user server-side. Tools read this — never a
    # user_id supplied by the LLM, so a user cannot make a tool operate on
    # someone else's data.
    set_current_user_id(user.id)

    agent = create_coach_agent()
    # Conversation memory is server-side, keyed by user. The client sends only
    # the new message; the SDK loads/saves history from the session store, so
    # the client cannot forge system/assistant turns (prompt injection).
    # Only the new user message is passed as input — a per-turn system message
    # would be persisted and duplicated across turns; the agent's `instructions`
    # already carry the system prompt.
    session = _user_session(user.id)
    result = await Runner.run(agent, input=body.message, session=session)
    reply: str = result.final_output or ""
    action = _parse_action(reply)

    return AgentChatResponse(reply=reply, action=action)


@router.post("/chat/clear", status_code=204)
async def clear_agent_chat(user: User = Depends(current_user)) -> None:
    """开始新对话：清空该用户的会话历史。"""
    _ensure_agent_path()
    await _user_session(user.id).clear_session()


def _user_session(user_id: str):
    from agents import SQLiteSession
    from shared.config import get_config

    db_path = get_config().data_dir / "agent_sessions.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return SQLiteSession(session_id=f"user_{user_id}", db_path=str(db_path))


# ─── Study plan output models (used by /study-plans/latest) ──────────────────

class StudyPlanDayOut(BaseModel):
    model_config = {"extra": "ignore"}  # tolerate legacy/extra keys in stored JSON

    index: int
    date: str | None = None
    theme: str = ""
    knowledge_points: list[str] = []
    kp_names: list[str] = []
    question_types: list[str] = []
    total_questions: int = 0
    note: str = ""
    paper_id: str
    paper_title: str


class StudyPlanOut(BaseModel):
    plan_id: str
    user_id: str
    total_days: int
    created_at: str
    days: list[StudyPlanDayOut]


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
