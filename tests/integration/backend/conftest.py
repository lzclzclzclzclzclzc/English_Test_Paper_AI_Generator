from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from uuid import uuid4

from backend.deps import reset_rate_limits
from backend.services import ai_gateway
from shared import storage
from shared.config import get_config, reset_config_cache
from shared.schemas import GenerateRequest, Paper, PaperItem, RevisedQuestion


def _fake_paper(user_query: str, *, mode="fresh", user_id=None, **_: object) -> Paper:
    total = 2 if "2" in user_query else 3
    questions = [
        RevisedQuestion(question_type="single_choice", answer="B", knowledge_point_ids=["kp_sc"]),
        RevisedQuestion(question_type="word_form", answer="written", knowledge_point_ids=["kp_wf"]),
        RevisedQuestion(
            question_type="sentence_rewriting",
            answer=[{"blank1": ["so"], "blank2": ["that"]}],
            knowledge_point_ids=["kp_sr"],
        ),
    ]
    return Paper(
        paper_id=uuid4().hex,
        title="test paper",
        generated_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        request=GenerateRequest(mode=mode, total_questions=total, user_id=user_id),
        items=[
            PaperItem(index=index, source_question_id=f"q_{index:05d}", revision_mode="original", question=question)
            for index, question in enumerate(questions[:total], start=1)
        ],
    )


def _fake_revise(paper: Paper, _: str) -> Paper:
    return paper.model_copy(update={"paper_id": uuid4().hex, "metadata": {"revised_from": paper.paper_id}})


@pytest.fixture
def client(tmp_path, monkeypatch):
    reset_rate_limits()
    db_path = tmp_path / "backend-test.db"
    storage.set_db_path(db_path)
    monkeypatch.setenv("SQLITE_PATH", str(db_path))
    reset_config_cache()
    monkeypatch.setenv("BACKEND_ENV", "test")
    monkeypatch.setenv("BCRYPT_ROUNDS", "4")
    monkeypatch.setattr(ai_gateway, "generate_paper", _fake_paper)
    monkeypatch.setattr(ai_gateway, "revise_paper", _fake_revise)
    monkeypatch.setattr(ai_gateway, "generate_solution", lambda *_args, **_kwargs: "答案解析")
    get_config()
    from backend.main import create_app

    app = create_app()
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
    storage.set_db_path(None)
    reset_rate_limits()
    reset_config_cache()


@pytest.fixture
def logged_in_client(client):
    response = client.post("/api/auth/register", json={"username": "demo", "password": "demo123"})
    assert response.status_code == 200
    return client


@pytest.fixture
def generated_paper(logged_in_client):
    response = logged_in_client.post("/api/papers/generate", json={"user_query": "来 3 道中等难度英语题", "mode": "fresh"})
    assert response.status_code == 200
    return response.json()
