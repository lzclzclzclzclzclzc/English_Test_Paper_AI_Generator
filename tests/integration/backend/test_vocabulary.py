from __future__ import annotations

import hashlib
import json
from datetime import timedelta

from shared import storage


def _seed_three_words(tmp_path) -> None:
    words = [
        {"id": "v_0001", "term": "accept", "part_of_speech": "v.", "meanings": ["接受"], "example_en": "Please accept the gift.", "example_zh": "请收下这份礼物。"},
        {"id": "v_0002", "term": "ability", "part_of_speech": "n.", "meanings": ["能力"], "example_en": "Practice builds ability.", "example_zh": "练习培养能力。"},
        {"id": "v_0003", "term": "above", "part_of_speech": "prep.", "meanings": ["在……上方"], "example_en": "The lamp is above the desk.", "example_zh": "灯在书桌上方。"},
    ]
    payload = {
        "metadata": {
            "id": "test-three", "label": "测试词表", "source_url": "https://example.test/list",
            "source_accessed_at": "2026-07-30", "source_sha256": hashlib.sha256(b"test-three").hexdigest(),
        },
        "words": words,
    }
    path = tmp_path / "words.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    assert storage.seed_vocabulary_from_json(path, expected_count=3) == 3


def _today_card(client) -> dict:
    response = client.get("/api/vocabulary/today")
    assert response.status_code == 200
    body = response.json()
    assert body["current_card"] is not None
    return body


def _judge(client, card: dict, rating: str):
    return client.post("/api/vocabulary/judgments", json={"word_id": card["word_id"], "rating": rating})


def test_prompt_hides_definition_and_fuzzy_words_repeat_until_known(logged_in_client, tmp_path):
    _seed_three_words(tmp_path)

    first = _today_card(logged_in_client)
    assert first["phase"] == "new"
    assert first["current_card"] == {"word_id": "v_0001", "term": "accept", "origin": "new", "retry_count": 0}
    assert "meanings" not in first["current_card"]

    fuzzy = _judge(logged_in_client, first["current_card"], "fuzzy")
    assert fuzzy.status_code == 200
    assert fuzzy.json()["detail"]["meanings"] == ["接受"]
    assert fuzzy.json()["detail"]["example_en"] == "Please accept the gift."
    assert fuzzy.json()["added_to_same_day_retry"] is True
    assert fuzzy.json()["counts"]["retry_pending"] == 1

    second = _today_card(logged_in_client)
    assert second["current_card"]["word_id"] == "v_0002"
    assert _judge(logged_in_client, second["current_card"], "known").status_code == 200
    third = _today_card(logged_in_client)
    assert _judge(logged_in_client, third["current_card"], "forgot").json()["phase"] == "same_day_retry"

    retry_one = _today_card(logged_in_client)
    assert retry_one["phase"] == "same_day_retry"
    assert retry_one["current_card"]["word_id"] == "v_0001"
    assert _judge(logged_in_client, retry_one["current_card"], "fuzzy").json()["counts"]["retry_pending"] == 2

    retry_two = _today_card(logged_in_client)
    assert retry_two["current_card"]["word_id"] == "v_0003"
    assert _judge(logged_in_client, retry_two["current_card"], "known").status_code == 200
    retry_three = _today_card(logged_in_client)
    assert retry_three["current_card"] == {"word_id": "v_0001", "term": "accept", "origin": "new", "retry_count": 1}
    complete = _judge(logged_in_client, retry_three["current_card"], "known")
    assert complete.json()["phase"] == "completed"
    assert logged_in_client.get("/api/vocabulary/today").json()["current_card"] is None


def test_stale_judgment_is_rejected_and_progress_tracks_retry(logged_in_client, tmp_path):
    _seed_three_words(tmp_path)
    first = _today_card(logged_in_client)
    assert _judge(logged_in_client, first["current_card"], "known").status_code == 200
    stale = _judge(logged_in_client, first["current_card"], "known")
    assert stale.status_code == 422

    progress = logged_in_client.get("/api/vocabulary/progress")
    assert progress.status_code == 200
    assert progress.json()["new_completed"] == 1
    assert progress.json()["same_day_retry_pending"] == 0
    assert progress.json()["total_words"] == 3
    assert progress.json()["learned_count"] == 1
    assert progress.json()["mastered_count"] == 0


def test_national_core_new_words_take_priority_and_progress_keeps_learning_separate(logged_in_client, tmp_path):
    payload = {
        "metadata": {
            "id": "test-merged", "label": "国家核心词 + 上海扩展词", "source_url": "https://example.test/core",
            "source_accessed_at": "2026-08-05", "source_sha256": hashlib.sha256(b"test-merged").hexdigest(),
            "expected_count": 2,
            "sources": [
                {"category": "national_core", "label": "国家核心词", "source_url": "https://example.test/core", "source_accessed_at": "2026-08-05", "source_sha256": "core"},
                {"category": "shanghai_extension", "label": "上海扩展词", "source_url": "https://example.test/shanghai", "source_accessed_at": "2026-08-05", "source_sha256": "extension"},
            ],
        },
        "words": [
            {"id": "extension_first", "term": "zebra", "part_of_speech": "n.", "meanings": ["斑马"], "example_en": "A zebra runs.", "example_zh": "斑马在奔跑。", "source_category": "shanghai_extension"},
            {"id": "core_later", "term": "apple", "part_of_speech": "n.", "meanings": ["苹果"], "example_en": "An apple is red.", "example_zh": "苹果是红色的。", "source_category": "national_core"},
        ],
    }
    path = tmp_path / "merged.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    storage.seed_vocabulary_from_json(path)

    first = _today_card(logged_in_client)
    assert first["current_card"]["word_id"] == "core_later"
    assert _judge(logged_in_client, first["current_card"], "known").status_code == 200
    progress = logged_in_client.get("/api/vocabulary/progress").json()
    assert progress["learned_count"] == 1
    assert progress["mastered_count"] == 0
    assert [item["category"] for item in progress["wordlist_sources"]] == ["national_core", "shanghai_extension"]

    user_id = logged_in_client.get("/api/auth/me").json()["id"]
    with storage.connect() as conn:
        conn.execute("UPDATE vocabulary_progress SET stage = 5 WHERE user_id = ? AND word_id = ?", (user_id, "core_later"))
    progress = logged_in_client.get("/api/vocabulary/progress").json()
    assert progress["learned_count"] == 1
    assert progress["mastered_count"] == 1


def test_due_reviews_take_priority_before_new_words(logged_in_client, tmp_path):
    _seed_three_words(tmp_path)
    user_id = logged_in_client.get("/api/auth/me").json()["id"]
    now = storage._vocabulary_now()
    first = storage.get_vocabulary_today(user_id, now)
    storage.judge_vocabulary_card(user_id, first["current_card"]["word_id"], "known", now)

    tomorrow = now + timedelta(days=1, minutes=1)
    next_day = storage.get_vocabulary_today(user_id, tomorrow)
    assert next_day["phase"] == "scheduled_review"
    assert next_day["current_card"]["word_id"] == "v_0001"


def test_vocabulary_settings_validate(logged_in_client, tmp_path):
    _seed_three_words(tmp_path)
    assert logged_in_client.patch("/api/vocabulary/settings", json={"daily_new_limit": 10}).json() == {
        "daily_new_limit": 10,
        "today_new_cards_added": 3,
    }
    assert logged_in_client.patch("/api/vocabulary/settings", json={"daily_new_limit": 9}).status_code == 422


def test_increasing_daily_goal_appends_new_cards_today(logged_in_client, tmp_path):
    words = [
        {
            "id": f"v_{index:04d}", "term": f"term{index}", "part_of_speech": "n.",
            "meanings": [f"释义{index}"], "example_en": f"Term {index} is here.", "example_zh": f"词{index}在这里。",
        }
        for index in range(1, 13)
    ]
    payload = {
        "metadata": {
            "id": "test-twelve", "label": "测试词表", "source_url": "https://example.test/list",
            "source_accessed_at": "2026-08-05", "source_sha256": hashlib.sha256(b"test-twelve").hexdigest(),
        },
        "words": words,
    }
    path = tmp_path / "twelve.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    storage.seed_vocabulary_from_json(path, expected_count=12)

    first = logged_in_client.patch("/api/vocabulary/settings", json={"daily_new_limit": 10})
    assert first.json()["today_new_cards_added"] == 10
    expanded = logged_in_client.patch("/api/vocabulary/settings", json={"daily_new_limit": 12})
    assert expanded.json() == {"daily_new_limit": 12, "today_new_cards_added": 2}
    assert logged_in_client.get("/api/vocabulary/today").json()["counts"]["new_total"] == 12


def test_vocabulary_meaning_normalization_removes_source_trailing_punctuation():
    assert storage._normalize_vocabulary_meaning("first;") == "first"
    assert storage._normalize_vocabulary_meaning("second\uFF1B  ") == "second"
    assert storage._normalize_vocabulary_meaning("first; second") == "first; second"
