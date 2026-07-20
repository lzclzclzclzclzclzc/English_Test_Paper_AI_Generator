from __future__ import annotations


def test_empty_mastery_profile(logged_in_client):
    response = logged_in_client.get("/api/users/me/mastery")
    assert response.status_code == 200
    assert response.json()["total_attempts_considered"] == 0
    assert response.json()["weak_kps"] == []


def test_mastery_uses_attempt_history(logged_in_client, generated_paper):
    answers = [{"index": item["index"], "user_answer": "wrong"} for item in generated_paper["items"]]
    logged_in_client.post("/api/attempts", json={"paper_id": generated_paper["paper_id"], "items": answers})

    response = logged_in_client.get("/api/users/me/mastery")
    assert response.status_code == 200
    body = response.json()
    assert body["total_attempts_considered"] == 3
    assert body["weak_kps"]
    assert body["dominant_types"]
