from __future__ import annotations


def test_submit_attempt_grades_and_marks_paper_submitted(logged_in_client, generated_paper):
    answers = [
        {"index": 1, "user_answer": "b"},
        {"index": 2, "user_answer": " written. "},
        {"index": 3, "user_answer": {"blank1": "so", "blank2": "that"}},
    ]
    response = logged_in_client.post("/api/attempts", json={"paper_id": generated_paper["paper_id"], "items": answers})
    assert response.status_code == 200
    body = response.json()
    assert body["attempt_id"]
    assert [item["is_correct"] for item in body["items"]] == [True, True, True]

    listing = logged_in_client.get("/api/papers").json()
    assert listing["items"][0]["submitted"] is True


def test_repeat_submission_is_allowed(logged_in_client, generated_paper):
    answers = [
        {"index": 1, "user_answer": "B"},
        {"index": 2, "user_answer": "written"},
        {"index": 3, "user_answer": ["so", "that"]},
    ]
    first = logged_in_client.post("/api/attempts", json={"paper_id": generated_paper["paper_id"], "items": answers})
    second = logged_in_client.post("/api/attempts", json={"paper_id": generated_paper["paper_id"], "items": answers})
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["attempt_id"] != second.json()["attempt_id"]


def test_unknown_item_index_returns_request_invalid(logged_in_client, generated_paper):
    response = logged_in_client.post(
        "/api/attempts",
        json={"paper_id": generated_paper["paper_id"], "items": [{"index": 999, "user_answer": "A"}]},
    )
    assert response.status_code == 422
    assert response.json()["error_code"] == "request.invalid"
