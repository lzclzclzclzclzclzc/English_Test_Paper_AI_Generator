from __future__ import annotations

import hashlib
import json

from shared import storage


def _seed_three_words(tmp_path) -> None:
    words = [
        {"id": "v_0001", "term": "accept", "part_of_speech": "v.", "meanings": ["接受"], "example_en": "Please accept the gift.", "example_zh": "请收下这份礼物。"},
        {"id": "v_0002", "term": "ability", "part_of_speech": "n.", "meanings": ["能力"], "example_en": "Practice builds ability.", "example_zh": "练习培养能力。"},
        {"id": "v_0003", "term": "above", "part_of_speech": "prep.", "meanings": ["在……上方"], "example_en": "The lamp is above the desk.", "example_zh": "灯在书桌上方。"},
    ]
    payload = {
        "metadata": {
            "id": "test-three",
            "label": "测试词表",
            "source_url": "https://example.test/list",
            "source_accessed_at": "2026-07-30",
            "source_sha256": hashlib.sha256(b"test-three").hexdigest(),
        },
        "words": words,
    }
    path = tmp_path / "words.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    assert storage.seed_vocabulary_from_json(path, expected_count=3) == 3


def test_today_assigns_new_words_and_reviews_are_user_scoped(logged_in_client, tmp_path):
    _seed_three_words(tmp_path)
    today = logged_in_client.get("/api/vocabulary/today")
    assert today.status_code == 200
    body = today.json()
    assert body["new_count"] == 3
    card = body["cards"][0]
    assert card["term"] == "accept"
    assert "accept" not in card["example_en"].lower()

    response = logged_in_client.post(
        "/api/vocabulary/reviews",
        json={"word_id": card["word_id"], "answer": " ACCEPT ", "rating": "known"},
    )
    assert response.status_code == 200
    assert response.json()["spelling_correct"] is True
    assert response.json()["applied_rating"] == "known"

    second = logged_in_client.post("/api/auth/register", json={"username": "other", "password": "demo123"})
    assert second.status_code == 200
    forbidden = logged_in_client.post(
        "/api/vocabulary/reviews",
        json={"word_id": card["word_id"], "answer": "accept", "rating": "known"},
    )
    assert forbidden.status_code == 422


def test_wrong_spelling_caps_known_at_fuzzy_and_settings_validate(logged_in_client, tmp_path):
    _seed_three_words(tmp_path)
    card = logged_in_client.get("/api/vocabulary/today").json()["cards"][0]
    response = logged_in_client.post(
        "/api/vocabulary/reviews",
        json={"word_id": card["word_id"], "answer": "accep", "rating": "known"},
    )
    assert response.status_code == 200
    assert response.json()["spelling_correct"] is False
    assert response.json()["applied_rating"] == "fuzzy"

    assert logged_in_client.patch("/api/vocabulary/settings", json={"daily_new_limit": 10}).json() == {"daily_new_limit": 10}
    assert logged_in_client.patch("/api/vocabulary/settings", json={"daily_new_limit": 9}).status_code == 422
    progress = logged_in_client.get("/api/vocabulary/progress")
    assert progress.status_code == 200
    assert progress.json()["new_completed"] == 1
    assert progress.json()["total_words"] == 3
