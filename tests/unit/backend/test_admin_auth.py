from __future__ import annotations

import pytest
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient

from backend.deps import current_user, require_admin
from backend.errors import AuthorizationError, BackendError, install_error_handlers
from backend.schemas import User
from shared import storage
from backend.auth.password import hash_password


def test_authorization_error_is_403():
    exc = AuthorizationError()
    assert isinstance(exc, BackendError)
    assert exc.http_status == 403
    assert exc.error_code == "auth.forbidden"


@pytest.fixture
def client(tmp_path):
    storage.set_db_path(tmp_path / "a.db")
    storage.init_db()
    app = FastAPI()
    install_error_handlers(app)

    @app.get("/admin-only")
    async def admin_only(user: User = Depends(require_admin)):
        return {"ok": user.username}

    @app.get("/any")
    async def any_user(user: User = Depends(current_user)):
        return {"ok": user.username}

    with TestClient(app) as c:
        yield c
    storage.set_db_path(None)


def _login(client, username):
    storage.create_user(username, hash_password("secret1"))
    sid = storage.create_session(storage.get_user_by_username(username).id)
    client.cookies.set("session_id", sid)
    return sid


def test_require_admin_forbids_normal_user(client):
    _login(client, "normie")
    assert client.get("/admin-only").status_code == 403


def test_require_admin_allows_admin(client):
    _login(client, "boss")
    storage.set_user_role(storage.get_user_by_username("boss").id, "admin")
    assert client.get("/admin-only").status_code == 200


def test_banned_user_is_forbidden_everywhere(client):
    _login(client, "bad")
    storage.set_user_status(storage.get_user_by_username("bad").id, "banned")
    assert client.get("/any").status_code == 403
