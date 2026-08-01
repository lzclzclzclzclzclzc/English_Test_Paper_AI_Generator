from __future__ import annotations

import pytest
from backend.auth.password import hash_password, verify_password
from shared import storage


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
