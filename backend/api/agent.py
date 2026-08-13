from __future__ import annotations

import re
import sys
from pathlib import Path

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from backend.deps import current_user
from backend.errors import ResourceNotFoundError
from backend.schemas import (
    AgentChatRequest,
    AgentChatResponse,
    User,
    MindmapListItem,
    MindmapListResponse,
    MindmapDetail,
    MindmapCreateRequest,
    MindmapUpdateRequest,
    MindmapCreateResponse,
)
from shared import storage

router = APIRouter(prefix="/agent", tags=["agent"])

_PAPER_RE = re.compile(r'<paper_ready\s+paper_id="([^"]+)"\s*/>')
_MINDMAP_READY_RE = re.compile(r'<mindmap_ready\s+mindmap_id="([^"]+)"\s*/>')
_MINDMAP_UPDATED_RE = re.compile(r'<mindmap_updated\s*/>')


def _parse_action(reply: str, current_mindmap_id: str | None = None) -> dict | None:
    m = _PAPER_RE.search(reply)
    if m:
        return {"type": "open_paper", "paper_id": m.group(1)}
    m = _MINDMAP_READY_RE.search(reply)
    if m:
        return {"type": "open_mindmap", "mindmap_id": m.group(1)}
    if _MINDMAP_UPDATED_RE.search(reply) and current_mindmap_id:
        return {"type": "mindmap_updated", "mindmap_id": current_mindmap_id}
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
    from agent.tools import set_current_user_id, set_current_mindmap_id

    # Bind the authenticated user server-side. Tools read this — never a
    # user_id supplied by the LLM, so a user cannot make a tool operate on
    # someone else's data.
    set_current_user_id(user.id)

    # scope=mindmap: 校验该图属于当前用户后，绑定为“当前编辑的图”，
    # 并使用按图+token 隔离的独立会话（每次前端挂载生成新 token → 新对话）。
    # Conversation memory is server-side, keyed by user (and mindmap+token in
    # mindmap scope). The client sends only the new message; the SDK loads/saves
    # history from the session store, so the client cannot forge system/assistant
    # turns (prompt injection). Only the new user message is passed as input — a
    # per-turn system message would be persisted and duplicated across turns; the
    # agent's `instructions` already carry the system prompt.
    mindmap_id: str | None = None
    if body.scope == "mindmap":
        if not body.mindmap_id or not storage.get_mindmap(user.id, body.mindmap_id):
            raise ResourceNotFoundError("思维导图不存在或无权访问")
        mindmap_id = body.mindmap_id
        set_current_mindmap_id(mindmap_id)
        session = _mindmap_session(user.id, body.session_token or "default")
    else:
        set_current_mindmap_id(None)
        session = _user_session(user.id)

    agent = create_coach_agent()
    result = await Runner.run(agent, input=body.message, session=session)
    reply: str = result.final_output or ""
    action = _parse_action(reply, current_mindmap_id=mindmap_id)

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


def _mindmap_session(user_id: str, token: str):
    from agents import SQLiteSession
    from shared.config import get_config

    db_path = get_config().data_dir / "agent_sessions.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    safe = "".join(ch for ch in token if ch.isalnum() or ch in "-_")[:40] or "default"
    return SQLiteSession(session_id=f"user_{user_id}_mm_{safe}", db_path=str(db_path))


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


@router.get("/mindmaps", response_model=MindmapListResponse)
async def list_mindmaps_route(
    user: User = Depends(current_user),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> MindmapListResponse:
    rows = storage.list_mindmaps(user.id, limit=limit, offset=offset)
    return MindmapListResponse(items=[MindmapListItem(**r) for r in rows])


@router.get("/mindmaps/{mindmap_id}", response_model=MindmapDetail)
async def get_mindmap_route(mindmap_id: str, user: User = Depends(current_user)) -> MindmapDetail:
    mm = storage.get_mindmap(user.id, mindmap_id)
    if not mm:
        raise ResourceNotFoundError("思维导图不存在")
    return MindmapDetail(**mm)


@router.post("/mindmaps", response_model=MindmapCreateResponse)
async def create_mindmap_route(
    body: MindmapCreateRequest, user: User = Depends(current_user),
) -> MindmapCreateResponse:
    # 手动新建不设 knowledge_point（留空），避免列表里把标题当副标题重复展示；
    # agent 出图走 create_mindmap 工具，那里才用知识点名填充。
    mid = storage.save_mindmap(user.id, body.title, body.outline_md)
    return MindmapCreateResponse(id=mid)


@router.patch("/mindmaps/{mindmap_id}", response_model=MindmapDetail)
async def update_mindmap_route(
    mindmap_id: str, body: MindmapUpdateRequest, user: User = Depends(current_user),
) -> MindmapDetail:
    ok = storage.update_mindmap(user.id, mindmap_id,
                                outline_md=body.outline_md, title=body.title)
    if not ok:
        raise ResourceNotFoundError("思维导图不存在")
    mm = storage.get_mindmap(user.id, mindmap_id)
    if not mm:
        raise ResourceNotFoundError("思维导图不存在")
    return MindmapDetail(**mm)


@router.delete("/mindmaps/{mindmap_id}", status_code=204)
async def delete_mindmap_route(mindmap_id: str, user: User = Depends(current_user)) -> None:
    if not storage.delete_mindmap(user.id, mindmap_id):
        raise ResourceNotFoundError("思维导图不存在")
