from __future__ import annotations

from backend.errors import AuthorizationError, BackendError


def test_authorization_error_is_403():
    exc = AuthorizationError()
    assert isinstance(exc, BackendError)
    assert exc.http_status == 403
    assert exc.error_code == "auth.forbidden"
