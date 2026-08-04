from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from backend.auth.password import hash_password, verify_password
from backend.schemas import StoredAttempt, StoredAttemptItem
from shared import storage


def _item(kp, qt="single_choice", correct=True, idx=1):
    return StoredAttemptItem(
        index=idx,
        source_question_id=f"q_{idx:05d}",
        knowledge_point_ids=[kp] if isinstance(kp, str) else kp,
        question_type=qt,
        is_correct=correct,
    )


def _write(db, user_id, items, answered_at=None):
    db.write_attempt(
        StoredAttempt(
            user_id=user_id,
            paper_id="p_" + user_id,
            answered_at=answered_at or datetime.now(timezone.utc),
            items=items,
        )
    )


@pytest.fixture
def db(tmp_path):
    storage.set_db_path(tmp_path / "s.db")
    storage.init_db()
    yield storage
    storage.set_db_path(None)


def test_list_and_count_users_with_search(db):
    db.create_user("alice", "h")
    db.create_user("bob", "h")
    db.create_user("alina", "h")
    rows = db.list_users(q="ali", limit=10, offset=0)
    names = {r["username"] for r in rows}
    assert names == {"alice", "alina"}
    assert db.count_users(q="ali") == 2
    assert db.count_users(q="") == 3


def test_list_users_includes_counts(db):
    u = db.create_user("counter", "h")
    rows = db.list_users(q="counter", limit=10, offset=0)
    row = rows[0]
    assert row["paper_count"] == 0
    assert row["attempt_count"] == 0
    assert row["role"] == "user"
    assert row["status"] == "active"


def test_update_password_hash(db):
    u = db.create_user("pw", hash_password("old123"))
    db.update_password_hash(u.id, hash_password("new123"))
    rec = db.get_user_by_username("pw")
    assert verify_password("new123", rec.password_hash)
    assert not verify_password("old123", rec.password_hash)


def test_delete_sessions_by_user(db):
    u = db.create_user("sess", "h")
    sid = db.create_session(u.id)
    db.delete_sessions_by_user(u.id)
    assert db.get_session(sid) is None


def test_stats_counts(db):
    a = db.create_user("s1", "h")
    db.create_user("s2", "h")
    total = db.admin_counts()
    assert total["total_users"] == 2
    assert total["total_papers"] == 0
    assert total["total_attempts"] == 0
    assert total["new_users_today"] == 2  # both created just now


def test_users_timeseries_buckets_by_day(db):
    db.create_user("t1", "h")
    series = db.users_created_by_day(days=7)
    assert any(point["count"] >= 1 for point in series)
    assert all(set(point.keys()) == {"day", "count"} for point in series)


def test_get_user_counts(db):
    u = db.create_user("countme", "h")
    counts = db.get_user_counts(u.id)
    assert counts == {"paper_count": 0, "attempt_count": 0}
    # a missing user yields zeros too (defensive)
    assert db.get_user_counts("nonexistent") == {"paper_count": 0, "attempt_count": 0}


def test_usernames_by_ids_empty(db):
    assert db.usernames_by_ids([]) == {}


def test_usernames_by_ids_maps_existing(db):
    a = db.create_user("mapa", "h")
    b = db.create_user("mapb", "h")
    result = db.usernames_by_ids([a.id, b.id])
    assert result == {a.id: "mapa", b.id: "mapb"}


def test_usernames_by_ids_unknown_absent(db):
    a = db.create_user("mapc", "h")
    result = db.usernames_by_ids([a.id, "ghost"])
    assert result == {a.id: "mapc"}
    assert "ghost" not in result


def test_attempts_by_day_buckets_and_correct_rate(db):
    now = datetime.now(timezone.utc)
    yesterday = now - timedelta(days=1)
    # today: 1 correct + 1 wrong → rate 0.5
    _write(db, "u1", [_item("kp_a", correct=True, idx=1), _item("kp_a", correct=False, idx=2)], answered_at=now)
    # yesterday: 1 correct → rate 1.0
    _write(db, "u2", [_item("kp_a", correct=True, idx=1)], answered_at=yesterday)

    series = db.attempts_by_day(days=7)
    by_day = {p["day"]: p for p in series}
    assert all(set(p.keys()) == {"day", "attempts", "correct_rate"} for p in series)
    today_key = now.date().isoformat()
    assert by_day[today_key]["attempts"] == 2
    assert by_day[today_key]["correct_rate"] == 0.5
    assert by_day[yesterday.date().isoformat()]["correct_rate"] == 1.0


def test_attempts_by_day_window_excludes_old(db):
    old = datetime.now(timezone.utc) - timedelta(days=100)
    _write(db, "u1", [_item("kp_a", correct=True)], answered_at=old)
    assert db.attempts_by_day(days=7) == []


def test_question_type_accuracy_per_type_wilson(db):
    # single_choice: 8/10 ; word_form: 0/2
    for i in range(10):
        _write(db, "u1", [_item("kp_sc", qt="single_choice", correct=(i < 8), idx=1)])
    for i in range(2):
        _write(db, "u2", [_item("kp_wf", qt="word_form", correct=False, idx=1)])

    rows = db.question_type_accuracy()
    by_type = {r["question_type"]: r for r in rows}
    assert by_type["single_choice"]["total"] == 10
    assert by_type["word_form"]["total"] == 2
    # Wilson lower bound: high-sample 80% clearly beats all-wrong
    assert by_type["single_choice"]["accuracy"] > by_type["word_form"]["accuracy"]
    assert by_type["word_form"]["accuracy"] == 0.0  # 0 correct → 0.0


def test_question_type_accuracy_window(db):
    old = datetime.now(timezone.utc) - timedelta(days=100)
    _write(db, "u1", [_item("kp_a", qt="single_choice", correct=True)], answered_at=old)
    assert db.question_type_accuracy(window_days=7) == []
