from __future__ import annotations

import pytest

from shared import storage


@pytest.fixture
def db(tmp_path):
    storage.set_db_path(tmp_path / "t.db")
    storage.init_db()
    yield storage
    storage.set_db_path(None)


def _columns(table: str) -> set[str]:
    with storage.connect() as conn:
        return {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}


def test_users_has_role_column_default_user(db):
    assert "role" in _columns("users")
    user = db.create_user("alice", "hash")
    fetched = db.get_user_by_id(user.id)
    assert fetched.role == "user"


def test_init_db_is_idempotent(db):
    db.init_db()
    db.init_db()
    assert "role" in _columns("users")


def test_users_has_status_column_default_active(db):
    assert "status" in _columns("users")
    user = db.create_user("bob", "hash")
    fetched = db.get_user_by_id(user.id)
    assert fetched.status == "active"
