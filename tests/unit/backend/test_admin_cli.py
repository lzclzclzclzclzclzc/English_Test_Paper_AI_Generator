from __future__ import annotations

from backend import cli
from backend.auth.password import hash_password
from shared import storage


def test_promote_admin_sets_role(tmp_path):
    storage.set_db_path(tmp_path / "c.db")
    storage.init_db()
    storage.create_user("carol", hash_password("secret1"))
    rc = cli.main(["promote-admin", "--username", "carol"])
    assert rc == 0
    assert storage.get_user_by_username("carol").role == "admin"
    storage.set_db_path(None)


def test_promote_admin_missing_user_returns_nonzero(tmp_path):
    storage.set_db_path(tmp_path / "c2.db")
    storage.init_db()
    rc = cli.main(["promote-admin", "--username", "ghost"])
    assert rc != 0
    storage.set_db_path(None)
