from __future__ import annotations

from shared import storage


def _generate(logged_in_client, n: int = 2):
    response = logged_in_client.post(
        "/api/papers/generate", json={"user_query": f"来 {n} 道题", "mode": "fresh"}
    )
    assert response.status_code == 200
    return response.json()


def test_filter_by_question_type_match(logged_in_client):
    # The mock builds items including single_choice + word_form.
    p1 = _generate(logged_in_client)
    p2 = _generate(logged_in_client)
    generated_ids = {p1["paper_id"], p2["paper_id"]}

    listing = logged_in_client.get("/api/papers?question_type=single_choice")
    assert listing.status_code == 200
    items = listing.json()["items"]
    assert len(items) >= 1
    for item in items:
        assert item["paper_id"] in generated_ids


def test_filter_by_question_type_no_match(logged_in_client):
    _generate(logged_in_client)
    # The mock never builds a writing question.
    listing = logged_in_client.get("/api/papers?question_type=writing")
    assert listing.status_code == 200
    assert listing.json()["items"] == []


def test_filter_by_submitted(logged_in_client):
    p1 = _generate(logged_in_client)
    p2 = _generate(logged_in_client)
    generated_ids = {p1["paper_id"], p2["paper_id"]}

    # Nothing was submitted in this flow.
    unsubmitted = logged_in_client.get("/api/papers?submitted=false")
    assert unsubmitted.status_code == 200
    unsubmitted_ids = {item["paper_id"] for item in unsubmitted.json()["items"]}
    assert generated_ids.issubset(unsubmitted_ids)

    submitted = logged_in_client.get("/api/papers?submitted=true")
    assert submitted.status_code == 200
    submitted_ids = {item["paper_id"] for item in submitted.json()["items"]}
    assert generated_ids.isdisjoint(submitted_ids)


def test_filter_by_date_range_storage(logged_in_client):
    # generated_at is "now"; exercise the date SQL without crafting timestamps.
    p1 = _generate(logged_in_client)
    p2 = _generate(logged_in_client)
    generated_ids = {p1["paper_id"], p2["paper_id"]}
    user = storage.get_user_by_username("demo")

    future = storage.list_papers(user.id, start_date="2099-01-01")
    assert [item for item in future if item.paper_id in generated_ids] == []

    past = storage.list_papers(user.id, start_date="2000-01-01")
    past_ids = {item.paper_id for item in past}
    assert generated_ids.issubset(past_ids)
