from __future__ import annotations

import ai_engine


def test_generate_paper_persists_and_lists_summary(logged_in_client):
    response = logged_in_client.post("/api/papers/generate", json={"user_query": "来 2 道选择题", "mode": "fresh"})
    assert response.status_code == 200
    paper = response.json()
    assert paper["paper_id"]
    assert len(paper["items"]) == 2

    fetched = logged_in_client.get(f"/api/papers/{paper['paper_id']}")
    assert fetched.status_code == 200
    assert fetched.json()["paper_id"] == paper["paper_id"]

    listing = logged_in_client.get("/api/papers")
    assert listing.status_code == 200
    item = listing.json()["items"][0]
    assert item["paper_id"] == paper["paper_id"]
    assert "items" not in item


def test_generate_paper_preserves_retrieval_metadata(logged_in_client, monkeypatch):
    """The backend must retain Retriever/Reviser diagnostics for later inspection."""
    original_generate = ai_engine.generate_paper

    def generate_with_retrieval_metadata(*args, **kwargs):
        paper = original_generate(*args, **kwargs)
        return paper.model_copy(
            update={
                "metadata": {
                    "engine": "retriever-reviser",
                    "retrieval_warnings": ["bucket 'single_choice' short of 1 question"],
                    "retrieval_shortfall": {"single_choice": 1},
                }
            }
        )

    monkeypatch.setattr(ai_engine, "generate_paper", generate_with_retrieval_metadata)
    response = logged_in_client.post(
        "/api/papers/generate",
        json={"user_query": "generate 2 questions", "mode": "fresh"},
    )

    assert response.status_code == 200
    paper = response.json()
    assert paper["metadata"]["retrieval_shortfall"] == {"single_choice": 1}

    fetched = logged_in_client.get(f"/api/papers/{paper['paper_id']}")
    assert fetched.status_code == 200
    assert fetched.json()["metadata"] == paper["metadata"]


def test_user_cannot_read_other_users_paper(client):
    client.post("/api/auth/register", json={"username": "alice", "password": "demo123"})
    paper = client.post("/api/papers/generate", json={"user_query": "来 1 道题", "mode": "fresh"}).json()
    client.post("/api/auth/logout")

    client.post("/api/auth/register", json={"username": "bob", "password": "demo123"})
    response = client.get(f"/api/papers/{paper['paper_id']}")
    assert response.status_code == 404
    assert response.json()["error_code"] == "resource.not_found"


def test_revise_creates_new_paper_id(logged_in_client, generated_paper):
    response = logged_in_client.post(
        "/api/papers/revise",
        json={"paper_id": generated_paper["paper_id"], "user_instruction": "前三题简单一点"},
    )
    assert response.status_code == 200
    revised = response.json()
    assert revised["paper_id"] != generated_paper["paper_id"]
    assert revised["metadata"]["revised_from"] == generated_paper["paper_id"]
