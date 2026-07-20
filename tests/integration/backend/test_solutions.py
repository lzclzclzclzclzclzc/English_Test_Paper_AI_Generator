from __future__ import annotations


def test_solution_requires_login(client, generated_paper):
    client.post("/api/auth/logout")
    item = generated_paper["items"][0]
    response = client.post(
        "/api/solutions",
        json={
            "question": item["question"],
            "source_question_id": item["source_question_id"],
            "revision_mode": item["revision_mode"],
        },
    )
    assert response.status_code == 401


def test_solution_returns_text(logged_in_client, generated_paper):
    item = generated_paper["items"][0]
    response = logged_in_client.post(
        "/api/solutions",
        json={
            "question": item["question"],
            "source_question_id": item["source_question_id"],
            "revision_mode": item["revision_mode"],
        },
    )
    assert response.status_code == 200
    assert "答案" in response.json()["solution"]
