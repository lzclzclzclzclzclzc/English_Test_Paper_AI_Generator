from __future__ import annotations

import asyncio

from app import auth as payment_auth


def test_get_current_user_ignores_ambient_proxy(monkeypatch):
    """A system/proxy env must NOT hijack the local backend auth check.

    We set a bogus proxy and stub httpx.AsyncClient to capture its kwargs and
    return a 200 /me. If trust_env were True httpx would try the dead proxy;
    the fix constructs the client with trust_env=False, so the local
    payment->backend call bypasses any ambient proxy/env config.

    pytest-asyncio is not installed in this repo (no async test infra), so we
    drive the coroutine with asyncio.run inside a plain sync test.
    """
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:9")   # dead proxy
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:9")

    captured = {}

    class FakeResp:
        status_code = 200

        def json(self):
            return {"id": "u1", "username": "tester", "role": "admin"}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            captured.update(kwargs)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url, cookies=None):
            return FakeResp()

    monkeypatch.setattr(payment_auth.httpx, "AsyncClient", FakeClient)

    # settings: no dev-fake-user, so it takes the real /me path
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("PAYMENT_DEV_FAKE_USER", "")
    monkeypatch.setenv("MOCK_PAY", "true")

    from starlette.requests import Request

    scope = {"type": "http", "headers": [(b"cookie", b"session_id=abc")]}
    req = Request(scope)

    user = asyncio.run(payment_auth.get_current_user(req))
    assert user.username == "tester"
    assert user.role == "admin"
    assert captured.get("trust_env") is False   # THE fix
    get_settings.cache_clear()
