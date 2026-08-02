from __future__ import annotations

from fastapi import APIRouter, Cookie, Depends, Response, status
from sqlite3 import IntegrityError

from backend.auth.password import hash_password, verify_password
from backend.auth.session import COOKIE_NAME, clear_session_cookie, set_session_cookie
from backend.deps import current_user
from backend.errors import InvalidCredentialsError, UsernameConflictError
from backend.schemas import User, UserCredentials
from shared import storage
from shared.config import get_config

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=User)
async def register(credentials: UserCredentials, response: Response) -> User:
    if storage.get_user_by_username(credentials.username):
        raise UsernameConflictError()
    try:
        user = storage.create_user(credentials.username, hash_password(credentials.password))
    except IntegrityError as exc:
        raise UsernameConflictError() from exc
    session_id = storage.create_session(user.id, get_config().backend.session_ttl_days)
    set_session_cookie(response, session_id)
    return user


@router.post("/login", response_model=User)
async def login(credentials: UserCredentials, response: Response) -> User:
    record = storage.get_user_by_username(credentials.username)
    if not record or not verify_password(credentials.password, record.password_hash):
        raise InvalidCredentialsError()
    session_id = storage.create_session(record.id, get_config().backend.session_ttl_days)
    set_session_cookie(response, session_id)
    return User(id=record.id, username=record.username, created_at=record.created_at, role=record.role, status=record.status)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response, session_id: str | None = Cookie(default=None, alias=COOKIE_NAME)) -> Response:
    if session_id:
        storage.delete_session(session_id)
    clear_session_cookie(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=User)
async def me(user: User = Depends(current_user)) -> User:
    return user
