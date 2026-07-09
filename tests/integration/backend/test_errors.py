from __future__ import annotations

import ai_engine
from ai_engine.errors import LLMError, ParserError


def test_request_validation_errors_are_wrapped(client):
    response = client.post("/api/auth/register", json={"username": "ab", "password": "123"})
    assert response.status_code == 422
    body = response.json()
    assert body["error_code"] == "request.invalid"
    assert body["trace_id"]


def test_ai_parser_error_maps_to_error_code(logged_in_client, monkeypatch):
    def fail(*args, **kwargs):
        raise ParserError("bad prompt")

    monkeypatch.setattr(ai_engine, "generate_paper", fail)
    response = logged_in_client.post("/api/papers/generate", json={"user_query": "bad", "mode": "fresh"})
    assert response.status_code == 400
    assert response.json()["error_code"] == "ai.parser_failed"


def test_ai_llm_error_maps_to_502(logged_in_client, generated_paper, monkeypatch):
    def fail(*args, **kwargs):
        raise LLMError("timeout")

    monkeypatch.setattr(ai_engine, "generate_solution", fail)
    item = generated_paper["items"][0]
    response = logged_in_client.post(
        "/api/solutions",
        json={
            "question": item["question"],
            "source_question_id": item["source_question_id"],
            "revision_mode": item["revision_mode"],
        },
    )
    assert response.status_code == 502
    assert response.json()["error_code"] == "ai.llm_upstream"


def test_unhandled_exception_has_server_internal(logged_in_client, monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(ai_engine, "generate_paper", fail)
    response = logged_in_client.post("/api/papers/generate", json={"user_query": "boom", "mode": "fresh"})
    assert response.status_code == 500
    body = response.json()
    assert body["error_code"] == "server.internal"
    assert body["trace_id"]
