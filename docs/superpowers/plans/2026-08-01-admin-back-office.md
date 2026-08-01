# Admin Back-Office Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an admin back-office (admin manages other users) — user list/detail, stats dashboard with charts, manual membership management, and user operations (ban/reset-password/promote) — layered onto the existing session-cookie auth.

**Architecture:** Database-backed roles: `users` gains `role`(user/admin) + `status`(active/banned) columns via the existing `_apply_migrations` mechanism. The main backend (`:8000/api`) gains `/api/admin/*` endpoints behind a `require_admin` dependency + a new 403 `AuthorizationError`; the standalone payment service (`:8001/payapi`) gains `/payapi/admin/*` for memberships/orders, trusting the `role` field it reads from the main backend's `/api/auth/me`. The frontend adds a `/admin` route group behind a `RequireAdmin` guard in the same React app.

**Tech Stack:** Python 3.11+ / FastAPI / SQLite (`shared/storage.py`, `payment/app/db.py`) / pytest; React + Vite + TanStack Query + React Router + Tailwind + Recharts / vitest.

**Spec:** `docs/admin-design.md` (Spec G).

**Conventions (from CLAUDE.md):**
- Run tests with pytest, never `python <file>.py`. On Windows prefix `PYTHONIOENCODING=utf-8`.
- User-facing strings Chinese; comments English, matching surrounding density.
- `git` remote is `main`; work on branch `admin`.
- The frontend on this branch uses tokens `text-ink`/`bg-wash`/`text-accent`/`bg-tint`/`border-hairline`/`text-muted-ink`/`text-quiet` and `--font-display` (see `Sidebar.tsx`), **not** the older Spec F literal tokens. Match the real code.

---

## File Structure

**Backend (main, `data/questions.db`):**
- Modify `shared/storage.py` — migrations for `role`/`status`; user admin queries; `set_user_role`/`set_user_status`/`update_password_hash`/`delete_sessions_by_user`; stats queries.
- Modify `backend/schemas.py` — `User` gains `role`/`status`; new admin request/response models.
- Modify `backend/errors.py` — `AuthorizationError` (403).
- Modify `backend/deps.py` — `current_user` banned check; `require_admin`.
- Create `backend/api/admin.py` — `/api/admin/*` router.
- Modify `backend/main.py` — register admin router.
- Modify `backend/cli.py` — `promote-admin` subcommand.
- Modify `backend/services/ai_gateway.py` — (only if needed) reuse `build_profile` for detail; likely no change.

**Payment (`data/payment.db`):**
- Modify `payment/app/auth.py` — `AuthUser.role`; `require_admin`.
- Modify `payment/app/service.py` — extract `extend_membership`; admin list/detail/grant/revoke; order list.
- Create `payment/app/admin_routes.py` — `/payapi/admin/*` router.
- Modify `payment/app/main.py` — register admin router.
- Modify `payment/app/schemas.py` — admin request/response models.

**Frontend:**
- Modify `frontend/src/types/api.ts` — `User.role`/`status`; admin DTOs.
- Create `frontend/src/components/RequireAdmin.tsx`.
- Create `frontend/src/api/admin.ts`.
- Create `frontend/src/pages/admin/AdminLayout.tsx`, `AdminOverviewPage.tsx`, `AdminUsersPage.tsx`, `AdminUserDetailPage.tsx`, `AdminMembershipsPage.tsx`, `AdminOrdersPage.tsx`.
- Modify `frontend/src/routes.tsx` — `/admin` route group.
- Modify `frontend/src/components/Sidebar.tsx` — conditional admin entry.
- Modify `frontend/package.json` — add `recharts`.

**Tests:**
- Create `tests/unit/backend/test_admin.py`, `tests/unit/backend/test_admin_auth.py`.
- Create `payment/tests/test_admin.py`.
- Create `frontend/src/components/RequireAdmin.test.tsx`, `frontend/src/api/admin.test.ts`.

**Docs (final task):**
- Modify `docs/backend-design.md` §12; cross-reference Spec G in backend/frontend specs.

---

## Phase A — Backend permission foundation

### Task A1: Migration — add `users.role`

**Files:**
- Modify: `shared/storage.py`
- Test: `tests/unit/backend/test_admin.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/backend/__init__.py` (empty) if missing, then `tests/unit/backend/test_admin.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONIOENCODING=utf-8 python -m pytest tests/unit/backend/test_admin.py::test_users_has_role_column_default_user -v`
Expected: FAIL — `role` not in columns (and/or `User` has no `role`).

- [ ] **Step 3: Add the migration**

In `shared/storage.py`, near the top where `MIGRATION_ATTEMPT_ITEMS_ITEM_INDEX` is defined, add:

```python
MIGRATION_USERS_ROLE = "20260801_001_users_role"
```

Add the migration function (place it beside `_migrate_attempt_items_item_index`):

```python
def _migrate_users_role(conn: sqlite3.Connection) -> None:
    if not _table_exists(conn, "users"):
        return
    if "role" in _table_columns(conn, "users"):
        return
    conn.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'")
```

Register it in `_apply_migrations` (append to the `migrations` list):

```python
    migrations = [
        (MIGRATION_ATTEMPT_ITEMS_ITEM_INDEX, _migrate_attempt_items_item_index),
        (MIGRATION_USERS_ROLE, _migrate_users_role),
    ]
```

- [ ] **Step 4: Update `User` schema and reads (so the test's `.role` works)**

In `backend/schemas.py`, extend `User`:

```python
class User(BaseModel):
    id: str
    username: str
    created_at: datetime
    role: Literal["user", "admin"] = "user"
```

(Ensure `Literal` is imported — it already is.) In `shared/storage.py`, update `_row_to_user_record` to read role, and `get_user_by_id` to pass it through:

```python
def _row_to_user_record(row: sqlite3.Row | None) -> UserRecord | None:
    if row is None:
        return None
    return UserRecord(
        id=row["id"],
        username=row["username"],
        password_hash=row["password_hash"],
        created_at=_dt(row["created_at"]),
        role=row["role"] if "role" in row.keys() else "user",
    )


def get_user_by_id(user_id: str) -> User | None:
    init_db()
    with connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    record = _row_to_user_record(row)
    return User(id=record.id, username=record.username, created_at=record.created_at, role=record.role) if record else None
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `PYTHONIOENCODING=utf-8 python -m pytest tests/unit/backend/test_admin.py -v`
Expected: both PASS.

- [ ] **Step 6: Commit**

```bash
git add shared/storage.py backend/schemas.py tests/unit/backend/
git commit -m "feat(admin): add users.role column + expose role on User"
```

---

### Task A2: Migration — add `users.status`

**Files:**
- Modify: `shared/storage.py`, `backend/schemas.py`
- Test: `tests/unit/backend/test_admin.py`

- [ ] **Step 1: Write the failing test** (append to `test_admin.py`)

```python
def test_users_has_status_column_default_active(db):
    assert "status" in _columns("users")
    user = db.create_user("bob", "hash")
    fetched = db.get_user_by_id(user.id)
    assert fetched.status == "active"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONIOENCODING=utf-8 python -m pytest tests/unit/backend/test_admin.py::test_users_has_status_column_default_active -v`
Expected: FAIL — `status` not in columns.

- [ ] **Step 3: Add the migration**

In `shared/storage.py`:

```python
MIGRATION_USERS_STATUS = "20260801_002_users_status"


def _migrate_users_status(conn: sqlite3.Connection) -> None:
    if not _table_exists(conn, "users"):
        return
    if "status" in _table_columns(conn, "users"):
        return
    conn.execute("ALTER TABLE users ADD COLUMN status TEXT NOT NULL DEFAULT 'active'")
```

Append to the `migrations` list in `_apply_migrations`:

```python
        (MIGRATION_USERS_STATUS, _migrate_users_status),
```

- [ ] **Step 4: Update schema + reads**

In `backend/schemas.py` `User`:

```python
    status: Literal["active", "banned"] = "active"
```

In `shared/storage.py` `_row_to_user_record`, add:

```python
        status=row["status"] if "status" in row.keys() else "active",
```

and in `get_user_by_id`, pass `status=record.status` into the `User(...)`.

- [ ] **Step 5: Run tests**

Run: `PYTHONIOENCODING=utf-8 python -m pytest tests/unit/backend/test_admin.py -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add shared/storage.py backend/schemas.py tests/unit/backend/test_admin.py
git commit -m "feat(admin): add users.status column + expose status on User"
```

---

### Task A3: `AuthorizationError` (403)

**Files:**
- Modify: `backend/errors.py`
- Test: `tests/unit/backend/test_admin_auth.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/backend/test_admin_auth.py`:

```python
from __future__ import annotations

from backend.errors import AuthorizationError, BackendError


def test_authorization_error_is_403():
    exc = AuthorizationError()
    assert isinstance(exc, BackendError)
    assert exc.http_status == 403
    assert exc.error_code == "auth.forbidden"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONIOENCODING=utf-8 python -m pytest tests/unit/backend/test_admin_auth.py -v`
Expected: FAIL — `ImportError: cannot import name 'AuthorizationError'`.

- [ ] **Step 3: Add the error class**

In `backend/errors.py`, after `AuthenticationError`:

```python
class AuthorizationError(BackendError):
    error_code = "auth.forbidden"
    http_status = 403
    message = "无权访问"
```

- [ ] **Step 4: Run test**

Run: `PYTHONIOENCODING=utf-8 python -m pytest tests/unit/backend/test_admin_auth.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/errors.py tests/unit/backend/test_admin_auth.py
git commit -m "feat(admin): add AuthorizationError (403 auth.forbidden)"
```

---

### Task A4: `require_admin` dependency + banned check in `current_user`

**Files:**
- Modify: `backend/deps.py`
- Modify: `backend/auth/routes.py` (login returns role/status; `/me` already returns `User`)
- Test: `tests/unit/backend/test_admin_auth.py`

- [ ] **Step 1: Write the failing tests** (append to `test_admin_auth.py`)

```python
import pytest
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient

from backend.deps import current_user, require_admin
from backend.errors import install_error_handlers
from backend.schemas import User
from shared import storage
from backend.auth.password import hash_password


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONIOENCODING=utf-8 python -m pytest tests/unit/backend/test_admin_auth.py -v`
Expected: FAIL — `require_admin` / `set_user_role` / `set_user_status` not defined.

- [ ] **Step 3: Add storage helpers** (`shared/storage.py`)

```python
def set_user_role(user_id: str, role: str) -> None:
    init_db()
    with connect() as conn:
        conn.execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))


def set_user_status(user_id: str, status: str) -> None:
    init_db()
    with connect() as conn:
        conn.execute("UPDATE users SET status = ? WHERE id = ?", (status, user_id))
```

- [ ] **Step 4: Add banned check + `require_admin`** (`backend/deps.py`)

Import the error at top: `from backend.errors import AuthenticationError, AuthorizationError, RateLimitError`.

In `current_user`, after resolving `user` (before `slide_session`), add:

```python
    if user.status == "banned":
        raise AuthorizationError("account banned")
```

Add the dependency (after `current_user`):

```python
async def require_admin(user: User = Depends(current_user)) -> User:
    if user.role != "admin":
        raise AuthorizationError()
    return user
```

- [ ] **Step 5: Run tests**

Run: `PYTHONIOENCODING=utf-8 python -m pytest tests/unit/backend/test_admin_auth.py -v`
Expected: all PASS.

- [ ] **Step 6: Ensure login returns role/status** (`backend/auth/routes.py`)

The `login` handler constructs `User(...)` manually — update it to pass role/status:

```python
    return User(id=record.id, username=record.username, created_at=record.created_at, role=record.role, status=record.status)
```

(Register/`/me` return the `User` from storage, which already carries the fields via Task A1/A2. Verify `create_user` returns default role/status — it builds a fresh `User()` so defaults `user`/`active` apply.)

- [ ] **Step 7: Run the whole backend suite (guard against regressions)**

Run: `PYTHONIOENCODING=utf-8 python -m pytest tests/unit/backend -v`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/deps.py backend/auth/routes.py shared/storage.py tests/unit/backend/test_admin_auth.py
git commit -m "feat(admin): require_admin dependency + banned-user gating"
```

---

### Task A5: CLI `promote-admin`

**Files:**
- Modify: `backend/cli.py`
- Test: `tests/unit/backend/test_admin_cli.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/backend/test_admin_cli.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONIOENCODING=utf-8 python -m pytest tests/unit/backend/test_admin_cli.py -v`
Expected: FAIL — `promote-admin` is not a valid subcommand (SystemExit) / not handled.

- [ ] **Step 3: Add the subcommand** (`backend/cli.py`)

Register parser (after `create_user` parser):

```python
    promote = sub.add_parser("promote-admin")
    promote.add_argument("--username", required=True)
```

Handle it (before the final `return 1`):

```python
    if args.command == "promote-admin":
        storage.init_db()
        record = storage.get_user_by_username(args.username)
        if record is None:
            print(json.dumps({"error": "user_not_found", "username": args.username}, ensure_ascii=False))
            return 2
        storage.set_user_role(record.id, "admin")
        print(json.dumps({"promoted": args.username}, ensure_ascii=False))
        return 0
```

- [ ] **Step 4: Run test**

Run: `PYTHONIOENCODING=utf-8 python -m pytest tests/unit/backend/test_admin_cli.py -v`
Expected: both PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/cli.py tests/unit/backend/test_admin_cli.py
git commit -m "feat(admin): add promote-admin CLI subcommand"
```

---

## Phase B — Main backend admin API

### Task B1: Storage — user list/count/detail + password + session-wipe

**Files:**
- Modify: `shared/storage.py`
- Test: `tests/unit/backend/test_admin_storage.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/backend/test_admin_storage.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONIOENCODING=utf-8 python -m pytest tests/unit/backend/test_admin_storage.py -v`
Expected: FAIL — `list_users` etc. not defined.

- [ ] **Step 3: Add storage helpers** (`shared/storage.py`)

```python
def list_users(q: str = "", limit: int = 50, offset: int = 0) -> list[dict]:
    init_db()
    like = f"%{q}%"
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT u.id, u.username, u.created_at, u.role, u.status,
                   (SELECT COUNT(*) FROM papers p WHERE p.user_id = u.id) AS paper_count,
                   (SELECT COUNT(*) FROM attempts a WHERE a.user_id = u.id) AS attempt_count
            FROM users u
            WHERE u.username LIKE ?
            ORDER BY u.created_at DESC
            LIMIT ? OFFSET ?
            """,
            (like, limit, offset),
        ).fetchall()
    return [dict(r) for r in rows]


def count_users(q: str = "") -> int:
    init_db()
    with connect() as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM users WHERE username LIKE ?", (f"%{q}%",)
        ).fetchone()[0]


def update_password_hash(user_id: str, password_hash: str) -> None:
    init_db()
    with connect() as conn:
        conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (password_hash, user_id))


def delete_sessions_by_user(user_id: str) -> None:
    init_db()
    with connect() as conn:
        conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
```

- [ ] **Step 4: Run test**

Run: `PYTHONIOENCODING=utf-8 python -m pytest tests/unit/backend/test_admin_storage.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add shared/storage.py tests/unit/backend/test_admin_storage.py
git commit -m "feat(admin): storage helpers for user list/count/password/session-wipe"
```

---

### Task B2: Storage — stats (overview counts + timeseries)

**Files:**
- Modify: `shared/storage.py`
- Test: `tests/unit/backend/test_admin_storage.py`

- [ ] **Step 1: Write the failing test** (append)

```python
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
    # one bucket for today with count >= 1
    assert any(point["count"] >= 1 for point in series)
    assert all(set(point.keys()) == {"day", "count"} for point in series)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONIOENCODING=utf-8 python -m pytest tests/unit/backend/test_admin_storage.py -k stats -v`
Expected: FAIL — `admin_counts` / `users_created_by_day` not defined.

- [ ] **Step 3: Add stats helpers** (`shared/storage.py`)

```python
def admin_counts() -> dict:
    init_db()
    today = datetime.now(timezone.utc).date().isoformat()
    with connect() as conn:
        total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        new_today = conn.execute(
            "SELECT COUNT(*) FROM users WHERE substr(created_at, 1, 10) = ?", (today,)
        ).fetchone()[0]
        total_papers = conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0]
        total_attempts = conn.execute("SELECT COUNT(*) FROM attempts").fetchone()[0]
    return {
        "total_users": total_users,
        "new_users_today": new_today,
        "total_papers": total_papers,
        "total_attempts": total_attempts,
    }


def _by_day(conn: sqlite3.Connection, table: str, ts_col: str, days: int) -> list[dict]:
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    rows = conn.execute(
        f"""
        SELECT substr({ts_col}, 1, 10) AS day, COUNT(*) AS count
        FROM {table}
        WHERE {ts_col} >= ?
        GROUP BY day
        ORDER BY day
        """,
        (since,),
    ).fetchall()
    return [{"day": r["day"], "count": r["count"]} for r in rows]


def users_created_by_day(days: int = 30) -> list[dict]:
    init_db()
    with connect() as conn:
        return _by_day(conn, "users", "created_at", days)


def papers_created_by_day(days: int = 30) -> list[dict]:
    init_db()
    with connect() as conn:
        return _by_day(conn, "papers", "generated_at", days)
```

- [ ] **Step 4: Run test**

Run: `PYTHONIOENCODING=utf-8 python -m pytest tests/unit/backend/test_admin_storage.py -k stats -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add shared/storage.py tests/unit/backend/test_admin_storage.py
git commit -m "feat(admin): storage stats (overview counts + per-day timeseries)"
```

---

### Task B3: Admin schemas

**Files:**
- Modify: `backend/schemas.py`
- Test: (covered by B4 endpoint tests)

- [ ] **Step 1: Add response/request models** (`backend/schemas.py`, near other models)

```python
class AdminUserListItem(BaseModel):
    id: str
    username: str
    created_at: datetime
    role: Literal["user", "admin"]
    status: Literal["active", "banned"]
    paper_count: int
    attempt_count: int


class AdminUserList(BaseModel):
    items: list[AdminUserListItem]
    total: int


class AdminUserDetail(BaseModel):
    id: str
    username: str
    created_at: datetime
    role: Literal["user", "admin"]
    status: Literal["active", "banned"]
    paper_count: int
    attempt_count: int
    correct_rate: float | None            # None when no attempt items
    membership_expires_at: str | None     # from payment; None if unknown/unavailable


class SetRoleRequest(BaseModel):
    role: Literal["user", "admin"]


class ResetPasswordRequest(BaseModel):
    new_password: str = Field(min_length=6, max_length=128)


class AdminOverview(BaseModel):
    total_users: int
    new_users_today: int
    total_papers: int
    total_attempts: int
    active_members: int | None            # None if payment unavailable


class TimeseriesPoint(BaseModel):
    day: str
    count: int


class AdminTimeseries(BaseModel):
    users_by_day: list[TimeseriesPoint]
    papers_by_day: list[TimeseriesPoint]
```

- [ ] **Step 2: Commit**

```bash
git add backend/schemas.py
git commit -m "feat(admin): admin API request/response schemas"
```

---

### Task B4: Admin router — users (list/detail/role/reset-password/ban/unban)

**Files:**
- Create: `backend/api/admin.py`
- Modify: `backend/main.py`
- Modify: `shared/storage.py` (correct-rate helper)
- Test: `tests/unit/backend/test_admin_api.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/backend/test_admin_api.py`:

```python
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.main import create_app
from backend.auth.password import hash_password
from shared import storage


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("BACKEND_ENV", "test")
    from shared.config import reset_config_cache
    reset_config_cache()
    storage.set_db_path(tmp_path / "api.db")
    storage.init_db()
    app = create_app()
    with TestClient(app) as c:
        yield c
    storage.set_db_path(None)
    reset_config_cache()


def _mk(client, username, admin=False):
    storage.create_user(username, hash_password("secret1"))
    u = storage.get_user_by_username(username)
    if admin:
        storage.set_user_role(u.id, "admin")
    return u


def _as(client, u):
    sid = storage.create_session(u.id)
    client.cookies.set("session_id", sid)


def test_users_list_requires_admin(client):
    normie = _mk(client, "normie")
    _as(client, normie)
    assert client.get("/api/admin/users").status_code == 403


def test_users_list_ok_for_admin(client):
    boss = _mk(client, "boss", admin=True)
    _mk(client, "u1")
    _as(client, boss)
    r = client.get("/api/admin/users?q=u1")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    assert data["items"][0]["username"] == "u1"


def test_set_role_cannot_change_self(client):
    boss = _mk(client, "boss", admin=True)
    _as(client, boss)
    r = client.post(f"/api/admin/users/{boss.id}/role", json={"role": "user"})
    assert r.status_code == 400


def test_reset_password_and_wipe_sessions(client):
    boss = _mk(client, "boss", admin=True)
    victim = _mk(client, "victim")
    victim_sid = storage.create_session(victim.id)
    _as(client, boss)
    r = client.post(f"/api/admin/users/{victim.id}/reset-password", json={"new_password": "brandnew1"})
    assert r.status_code == 200
    assert storage.get_session(victim_sid) is None
    assert storage.get_user_by_username("victim").password_hash != victim.username


def test_ban_and_unban(client):
    boss = _mk(client, "boss", admin=True)
    victim = _mk(client, "victim")
    victim_sid = storage.create_session(victim.id)
    _as(client, boss)
    assert client.post(f"/api/admin/users/{victim.id}/ban").status_code == 200
    assert storage.get_session(victim_sid) is None
    assert storage.get_user_by_id(victim.id).status == "banned"
    assert client.post(f"/api/admin/users/{victim.id}/unban").status_code == 200
    assert storage.get_user_by_id(victim.id).status == "active"


def test_cannot_ban_self(client):
    boss = _mk(client, "boss", admin=True)
    _as(client, boss)
    assert client.post(f"/api/admin/users/{boss.id}/ban").status_code == 400
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONIOENCODING=utf-8 python -m pytest tests/unit/backend/test_admin_api.py -v`
Expected: FAIL — 404s (router not mounted).

- [ ] **Step 3: Add a correct-rate storage helper** (`shared/storage.py`)

```python
def user_correct_rate(user_id: str) -> float | None:
    init_db()
    with connect() as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) AS n, SUM(ai.is_correct) AS c
            FROM attempts a JOIN attempt_items ai ON ai.attempt_id = a.id
            WHERE a.user_id = ?
            """,
            (user_id,),
        ).fetchone()
    if not row or not row["n"]:
        return None
    return round((row["c"] or 0) / row["n"], 4)
```

- [ ] **Step 4: Create the router** (`backend/api/admin.py`)

```python
from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends

from backend.auth.password import hash_password
from backend.deps import require_admin
from backend.errors import ResourceNotFoundError, ValidationError
from backend.schemas import (
    AdminOverview,
    AdminTimeseries,
    AdminUserDetail,
    AdminUserList,
    ResetPasswordRequest,
    SetRoleRequest,
    User,
)
from shared import storage
from shared.config import get_config

router = APIRouter(prefix="/admin", tags=["admin"])


def _require_target(user_id: str) -> User:
    target = storage.get_user_by_id(user_id)
    if target is None:
        raise ResourceNotFoundError("user not found")
    return target


@router.get("/users", response_model=AdminUserList)
async def list_users(q: str = "", limit: int = 50, offset: int = 0, _: User = Depends(require_admin)) -> AdminUserList:
    items = storage.list_users(q=q, limit=limit, offset=offset)
    return AdminUserList(items=items, total=storage.count_users(q=q))


@router.get("/users/{user_id}", response_model=AdminUserDetail)
async def user_detail(user_id: str, _: User = Depends(require_admin)) -> AdminUserDetail:
    target = _require_target(user_id)
    rows = storage.list_users(q=target.username, limit=1, offset=0)
    counts = next((r for r in rows if r["id"] == user_id), {"paper_count": 0, "attempt_count": 0})
    return AdminUserDetail(
        id=target.id,
        username=target.username,
        created_at=target.created_at,
        role=target.role,
        status=target.status,
        paper_count=counts["paper_count"],
        attempt_count=counts["attempt_count"],
        correct_rate=storage.user_correct_rate(user_id),
        membership_expires_at=_fetch_membership_expiry(user_id),
    )


@router.post("/users/{user_id}/role", response_model=User)
async def set_role(user_id: str, body: SetRoleRequest, admin: User = Depends(require_admin)) -> User:
    if user_id == admin.id:
        raise ValidationError("cannot change your own role")
    _require_target(user_id)
    storage.set_user_role(user_id, body.role)
    return storage.get_user_by_id(user_id)


@router.post("/users/{user_id}/reset-password", response_model=User)
async def reset_password(user_id: str, body: ResetPasswordRequest, _: User = Depends(require_admin)) -> User:
    _require_target(user_id)
    storage.update_password_hash(user_id, hash_password(body.new_password))
    storage.delete_sessions_by_user(user_id)
    return storage.get_user_by_id(user_id)


@router.post("/users/{user_id}/ban", response_model=User)
async def ban(user_id: str, admin: User = Depends(require_admin)) -> User:
    if user_id == admin.id:
        raise ValidationError("cannot ban yourself")
    _require_target(user_id)
    storage.set_user_status(user_id, "banned")
    storage.delete_sessions_by_user(user_id)
    return storage.get_user_by_id(user_id)


@router.post("/users/{user_id}/unban", response_model=User)
async def unban(user_id: str, _: User = Depends(require_admin)) -> User:
    _require_target(user_id)
    storage.set_user_status(user_id, "active")
    return storage.get_user_by_id(user_id)


def _payment_base() -> str:
    return get_config().payment_url if hasattr(get_config(), "payment_url") else "http://localhost:8001"


def _fetch_membership_expiry(user_id: str) -> str | None:
    # Best-effort cross-service read; payment down → None (non-blocking).
    try:
        resp = httpx.get(f"{_payment_base()}/payapi/admin/memberships/{user_id}", timeout=3.0)
        if resp.status_code == 200:
            return resp.json().get("expires_at")
    except httpx.HTTPError:
        return None
    return None
```

> Note: the cross-service call in `user_detail` cannot forward the admin's cookie from a sync helper cleanly; Task B6 replaces `_fetch_membership_expiry` with a cookie-forwarding version. For now it returns `None` when payment is unavailable, which keeps tests (no payment running) green.

- [ ] **Step 5: Register the router** (`backend/main.py`)

Add import: `from backend.api import admin as admin_api`.
After the other `include_router` lines:

```python
    app.include_router(admin_api.router, prefix="/api")
```

- [ ] **Step 6: Run test**

Run: `PYTHONIOENCODING=utf-8 python -m pytest tests/unit/backend/test_admin_api.py -v`
Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/api/admin.py backend/main.py shared/storage.py tests/unit/backend/test_admin_api.py
git commit -m "feat(admin): /api/admin/users endpoints (list/detail/role/reset-pw/ban)"
```

---

### Task B5: Admin router — stats (overview + timeseries)

**Files:**
- Modify: `backend/api/admin.py`
- Test: `tests/unit/backend/test_admin_api.py`

- [ ] **Step 1: Write the failing test** (append)

```python
def test_stats_overview_and_timeseries(client):
    boss = _mk(client, "boss", admin=True)
    _mk(client, "u1")
    _as(client, boss)
    ov = client.get("/api/admin/stats/overview")
    assert ov.status_code == 200
    assert ov.json()["total_users"] == 2
    ts = client.get("/api/admin/stats/timeseries?days=7")
    assert ts.status_code == 200
    body = ts.json()
    assert "users_by_day" in body and "papers_by_day" in body
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONIOENCODING=utf-8 python -m pytest tests/unit/backend/test_admin_api.py -k stats -v`
Expected: FAIL — 404.

- [ ] **Step 3: Add the endpoints** (`backend/api/admin.py`)

Add imports at top: `from backend.schemas import AdminOverview, AdminTimeseries` are already imported. Add:

```python
@router.get("/stats/overview", response_model=AdminOverview)
async def stats_overview(_: User = Depends(require_admin)) -> AdminOverview:
    counts = storage.admin_counts()
    return AdminOverview(**counts, active_members=_fetch_active_members())


@router.get("/stats/timeseries", response_model=AdminTimeseries)
async def stats_timeseries(days: int = 30, _: User = Depends(require_admin)) -> AdminTimeseries:
    return AdminTimeseries(
        users_by_day=storage.users_created_by_day(days),
        papers_by_day=storage.papers_created_by_day(days),
    )


def _fetch_active_members() -> int | None:
    try:
        resp = httpx.get(f"{_payment_base()}/payapi/admin/memberships?limit=100000", timeout=3.0)
        if resp.status_code == 200:
            items = resp.json().get("items", [])
            return sum(1 for m in items if m.get("active"))
    except httpx.HTTPError:
        return None
    return None
```

- [ ] **Step 4: Run test**

Run: `PYTHONIOENCODING=utf-8 python -m pytest tests/unit/backend/test_admin_api.py -k stats -v`
Expected: PASS (active_members is None with no payment running — allowed by schema).

- [ ] **Step 5: Commit**

```bash
git add backend/api/admin.py tests/unit/backend/test_admin_api.py
git commit -m "feat(admin): /api/admin/stats overview + timeseries"
```

---

## Phase C — Payment admin API

### Task C1: `AuthUser.role` + payment `require_admin`

**Files:**
- Modify: `payment/app/auth.py`
- Modify: `payment/app/config.py` (dev-fake role)
- Test: `payment/tests/test_admin.py`

- [ ] **Step 1: Write the failing test**

Create `payment/tests/test_admin.py` (follow existing `payment/tests/conftest.py` patterns):

```python
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from payment.app.main import create_app
from payment.app.config import get_settings


@pytest.fixture(autouse=True)
def _settings(tmp_path, monkeypatch):
    monkeypatch.setenv("MOCK_PAY", "true")
    monkeypatch.setenv("DB_PATH", str(tmp_path / "pay.db"))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _client_as(role: str) -> TestClient:
    # dev fake user carries a role via PAYMENT_DEV_FAKE_ROLE
    import os
    os.environ["PAYMENT_DEV_FAKE_USER"] = "tester"
    os.environ["PAYMENT_DEV_FAKE_ROLE"] = role
    get_settings.cache_clear()
    return TestClient(create_app())


def test_admin_memberships_forbidden_for_user():
    c = _client_as("user")
    assert c.get("/payapi/admin/memberships").status_code == 403


def test_admin_memberships_ok_for_admin():
    c = _client_as("admin")
    assert c.get("/payapi/admin/memberships").status_code == 200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONIOENCODING=utf-8 python -m pytest payment/tests/test_admin.py -v`
Expected: FAIL — no `require_admin`/route; `PAYMENT_DEV_FAKE_ROLE` unknown.

- [ ] **Step 3: Extend config** (`payment/app/config.py`)

Add to `Settings`:

```python
    payment_dev_fake_role: str = "user"
```

- [ ] **Step 4: Extend `AuthUser` + resolution + `require_admin`** (`payment/app/auth.py`)

Change the dataclass:

```python
@dataclass(frozen=True)
class AuthUser:
    id: str
    username: str
    role: str = "user"
```

In `get_current_user`, the dev-fake branch:

```python
    if settings.payment_dev_fake_user:
        name = settings.payment_dev_fake_user
        return AuthUser(id=f"dev-{name}", username=name, role=settings.payment_dev_fake_role)
```

And the real branch's final construction:

```python
    user = AuthUser(id=str(data["id"]), username=data["username"], role=data.get("role", "user"))
```

Add the dependency (bottom of file):

```python
async def require_admin(request: Request) -> AuthUser:
    user = await get_current_user(request)
    if user.role != "admin":
        raise PaymentError(403, "auth.forbidden", "无权访问")
    return user
```

- [ ] **Step 5: Create a minimal admin router so the 403/200 test can run** (`payment/app/admin_routes.py`)

```python
from fastapi import APIRouter, Depends

from . import service
from .auth import AuthUser, require_admin

admin_router = APIRouter(prefix="/payapi/admin")


@admin_router.get("/memberships")
def list_memberships(q: str = "", limit: int = 50, offset: int = 0, _: AuthUser = Depends(require_admin)) -> dict:
    return {"items": service.list_memberships(q, limit, offset), "total": service.count_memberships(q)}
```

Add stubs in `payment/app/service.py` (real impl in C2):

```python
def list_memberships(q: str = "", limit: int = 50, offset: int = 0) -> list[dict]:
    return []


def count_memberships(q: str = "") -> int:
    return 0
```

Register in `payment/app/main.py`:

```python
    from .admin_routes import admin_router
    app.include_router(admin_router)
```

(Place the import at top with the others and the `include_router` inside `create_app`.)

- [ ] **Step 6: Run test**

Run: `PYTHONIOENCODING=utf-8 python -m pytest payment/tests/test_admin.py -v`
Expected: both PASS.

- [ ] **Step 7: Commit**

```bash
git add payment/app/auth.py payment/app/config.py payment/app/admin_routes.py payment/app/service.py payment/app/main.py payment/tests/test_admin.py
git commit -m "feat(admin): payment require_admin + AuthUser.role + membership list stub"
```

---

### Task C2: Extract `extend_membership`; implement list/detail/grant/revoke + orders

**Files:**
- Modify: `payment/app/service.py`
- Modify: `payment/app/admin_routes.py`
- Modify: `payment/app/schemas.py`
- Test: `payment/tests/test_admin.py`, `payment/tests/test_membership.py` (regression)

- [ ] **Step 1: Write the failing tests** (append to `payment/tests/test_admin.py`)

```python
from payment.app import service
from payment.app.config import parse_iso, utcnow


def _seed_membership(user_id, expires_iso):
    from payment.app.db import get_conn, init_db
    init_db()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO memberships(user_id, expires_at, updated_at) VALUES(?,?,?)",
            (user_id, expires_iso, expires_iso),
        )


def test_extend_membership_from_scratch():
    from payment.app.db import init_db
    init_db()
    exp = service.extend_membership("newbie", 30)
    assert parse_iso(exp) > utcnow()


def test_grant_and_revoke_via_api():
    c = _client_as("admin")
    r = c.post("/payapi/admin/memberships/u42/grant", json={"days": 30})
    assert r.status_code == 200
    assert r.json()["active"] is True
    r2 = c.post("/payapi/admin/memberships/u42/revoke")
    assert r2.status_code == 200
    assert r2.json()["active"] is False


def test_orders_list_admin_only():
    assert _client_as("user").get("/payapi/admin/orders").status_code == 403
    assert _client_as("admin").get("/payapi/admin/orders").status_code == 200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONIOENCODING=utf-8 python -m pytest payment/tests/test_admin.py -v`
Expected: FAIL — `extend_membership`, grant/revoke/orders routes missing.

- [ ] **Step 3: Extract `extend_membership` and reuse in `mark_order_paid`** (`payment/app/service.py`)

Add:

```python
def extend_membership(user_id: str, days: int, now=None) -> str:
    """Push a user's membership expiry forward by `days`. Reused by both
    payment-success (mark_order_paid) and admin manual grant."""
    now = now or utcnow()
    with get_conn() as conn:
        current = conn.execute(
            "SELECT expires_at FROM memberships WHERE user_id=?", (user_id,)
        ).fetchone()
        base = now
        if current is not None:
            base = max(parse_iso(current["expires_at"]), now)
        new_expiry = format_iso(base + timedelta(days=days))
        conn.execute(
            "INSERT INTO memberships(user_id, expires_at, updated_at) VALUES(?,?,?)"
            " ON CONFLICT(user_id) DO UPDATE SET"
            " expires_at=excluded.expires_at, updated_at=excluded.updated_at",
            (user_id, new_expiry, format_iso(now)),
        )
    return new_expiry
```

Refactor `mark_order_paid` to reuse it: replace the membership block (lines computing `base`/`new_expiry` + UPSERT) with a call. Because `mark_order_paid` runs inside its own `with get_conn()` for the CAS, keep the CAS transaction, then after confirming `rowcount == 1` and reading `user_id, plan_id`, call `extend_membership(user_id, plan.duration_days, now)` (it opens its own connection — acceptable; the CAS already committed the PAID state).

> Verify `mark_order_paid` still passes its existing tests (`test_orders_mock.py`) after refactor — idempotency is preserved because the CAS still guards the single PAID transition.

Add list/detail/revoke helpers:

```python
def list_memberships(q: str = "", limit: int = 50, offset: int = 0) -> list[dict]:
    like = f"%{q}%"
    now = utcnow_iso()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT user_id, expires_at FROM memberships WHERE user_id LIKE ?"
            " ORDER BY expires_at DESC LIMIT ? OFFSET ?",
            (like, limit, offset),
        ).fetchall()
    return [{"user_id": r["user_id"], "expires_at": r["expires_at"], "active": r["expires_at"] > now} for r in rows]


def count_memberships(q: str = "") -> int:
    with get_conn() as conn:
        return conn.execute("SELECT COUNT(*) FROM memberships WHERE user_id LIKE ?", (f"%{q}%",)).fetchone()[0]


def revoke_membership(user_id: str) -> dict:
    now = utcnow()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO memberships(user_id, expires_at, updated_at) VALUES(?,?,?)"
            " ON CONFLICT(user_id) DO UPDATE SET expires_at=excluded.expires_at, updated_at=excluded.updated_at",
            (user_id, format_iso(now), format_iso(now)),
        )
    return get_membership(user_id)


def list_orders(status: str | None = None, limit: int = 50, offset: int = 0) -> list[dict]:
    with get_conn() as conn:
        if status:
            rows = conn.execute(
                "SELECT * FROM orders WHERE status=? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (status, limit, offset),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM orders ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
    return [dict(r) for r in rows]
```

Ensure `utcnow_iso` is imported in service.py (it imports from `.config` already — add `utcnow_iso` to that import if absent).

- [ ] **Step 4: Add admin schemas** (`payment/app/schemas.py`)

```python
class GrantMembershipIn(BaseModel):
    days: int | None = None
    plan_id: str | None = None
```

- [ ] **Step 5: Flesh out the admin router** (`payment/app/admin_routes.py`)

```python
from fastapi import APIRouter, Depends

from . import service
from .auth import AuthUser, require_admin
from .plans import get_plan
from .schemas import GrantMembershipIn

admin_router = APIRouter(prefix="/payapi/admin")


@admin_router.get("/memberships")
def list_memberships(q: str = "", limit: int = 50, offset: int = 0, _: AuthUser = Depends(require_admin)) -> dict:
    return {"items": service.list_memberships(q, limit, offset), "total": service.count_memberships(q)}


@admin_router.get("/memberships/{user_id}")
def membership_detail(user_id: str, _: AuthUser = Depends(require_admin)) -> dict:
    return service.get_membership(user_id)


@admin_router.post("/memberships/{user_id}/grant")
def grant(user_id: str, body: GrantMembershipIn, _: AuthUser = Depends(require_admin)) -> dict:
    days = body.days if body.days is not None else get_plan(body.plan_id).duration_days
    service.extend_membership(user_id, days)
    return service.get_membership(user_id)


@admin_router.post("/memberships/{user_id}/revoke")
def revoke(user_id: str, _: AuthUser = Depends(require_admin)) -> dict:
    return service.revoke_membership(user_id)


@admin_router.get("/orders")
def list_orders(status: str | None = None, limit: int = 50, offset: int = 0, _: AuthUser = Depends(require_admin)) -> dict:
    return {"items": service.list_orders(status, limit, offset)}
```

- [ ] **Step 6: Run tests (admin + regression)**

Run: `PYTHONIOENCODING=utf-8 python -m pytest payment/tests -v`
Expected: all PASS (including `test_orders_mock.py`, `test_membership.py`).

- [ ] **Step 7: Commit**

```bash
git add payment/app/service.py payment/app/admin_routes.py payment/app/schemas.py payment/tests/test_admin.py
git commit -m "feat(admin): payment memberships grant/revoke/list + orders; extract extend_membership"
```

---

### Task C3: Cookie-forwarding cross-service reads in backend detail/overview

**Files:**
- Modify: `backend/api/admin.py`
- Test: `tests/unit/backend/test_admin_api.py` (monkeypatched)

- [ ] **Step 1: Write the failing test** (append to `test_admin_api.py`)

```python
def test_user_detail_includes_membership_when_payment_ok(client, monkeypatch):
    boss = _mk(client, "boss", admin=True)
    victim = _mk(client, "victim")
    _as(client, boss)

    import backend.api.admin as admin_mod

    def fake_fetch(user_id, cookie):
        return "2099-01-01T00:00:00Z"

    monkeypatch.setattr(admin_mod, "_fetch_membership_expiry", fake_fetch)
    r = client.get(f"/api/admin/users/{victim.id}")
    assert r.status_code == 200
    assert r.json()["membership_expires_at"] == "2099-01-01T00:00:00Z"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONIOENCODING=utf-8 python -m pytest tests/unit/backend/test_admin_api.py -k membership_when_payment -v`
Expected: FAIL — signature mismatch (`_fetch_membership_expiry` takes 1 arg / not called with cookie).

- [ ] **Step 3: Update the helper to forward the cookie** (`backend/api/admin.py`)

Change `user_detail` to read the request cookie and pass it, and update the helper signature:

```python
from fastapi import APIRouter, Depends, Request
from backend.auth.session import COOKIE_NAME
```

```python
@router.get("/users/{user_id}", response_model=AdminUserDetail)
async def user_detail(user_id: str, request: Request, _: User = Depends(require_admin)) -> AdminUserDetail:
    target = _require_target(user_id)
    rows = storage.list_users(q=target.username, limit=1, offset=0)
    counts = next((r for r in rows if r["id"] == user_id), {"paper_count": 0, "attempt_count": 0})
    cookie = request.cookies.get(COOKIE_NAME)
    return AdminUserDetail(
        id=target.id, username=target.username, created_at=target.created_at,
        role=target.role, status=target.status,
        paper_count=counts["paper_count"], attempt_count=counts["attempt_count"],
        correct_rate=storage.user_correct_rate(user_id),
        membership_expires_at=_fetch_membership_expiry(user_id, cookie),
    )
```

```python
def _fetch_membership_expiry(user_id: str, cookie: str | None) -> str | None:
    try:
        resp = httpx.get(
            f"{_payment_base()}/payapi/admin/memberships/{user_id}",
            cookies={COOKIE_NAME: cookie} if cookie else None,
            timeout=3.0,
        )
        if resp.status_code == 200:
            return resp.json().get("expires_at")
    except httpx.HTTPError:
        return None
    return None
```

Update `_fetch_active_members` similarly to accept/forward a cookie, and pass `request.cookies.get(COOKIE_NAME)` from `stats_overview` (add `request: Request` param).

- [ ] **Step 4: Run test**

Run: `PYTHONIOENCODING=utf-8 python -m pytest tests/unit/backend/test_admin_api.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/api/admin.py tests/unit/backend/test_admin_api.py
git commit -m "feat(admin): forward admin session cookie on cross-service membership reads"
```

---

## Phase D — Frontend

### Task D1: `User.role`/`status` type + admin DTOs + `api/admin.ts`

**Files:**
- Modify: `frontend/src/types/api.ts`
- Create: `frontend/src/api/admin.ts`
- Test: `frontend/src/api/admin.test.ts`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/api/admin.test.ts`:

```ts
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { listUsers, grantMembership } from '@/api/admin'

describe('admin api base-url routing', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('lists users via /api', async () => {
    const spy = vi.spyOn(global, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ items: [], total: 0 }), { status: 200 }),
    )
    await listUsers('bob')
    expect(spy).toHaveBeenCalledWith(expect.stringContaining('/api/admin/users'), expect.anything())
  })

  it('grants membership via /payapi', async () => {
    const spy = vi.spyOn(global, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ user_id: 'u', expires_at: null, active: true }), { status: 200 }),
    )
    await grantMembership('u', { days: 30 })
    expect(spy).toHaveBeenCalledWith(expect.stringContaining('/payapi/admin/memberships/u/grant'), expect.anything())
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/api/admin.test.ts`
Expected: FAIL — module `@/api/admin` not found.

- [ ] **Step 3: Extend `User` type** (`frontend/src/types/api.ts`)

```ts
export interface User {
  id: string
  username: string
  created_at: string
  role: 'user' | 'admin'
  status: 'active' | 'banned'
}
```

Append admin DTOs at the end of the file:

```ts
// ---- 管理后台 ----
export interface AdminUserListItem {
  id: string
  username: string
  created_at: string
  role: 'user' | 'admin'
  status: 'active' | 'banned'
  paper_count: number
  attempt_count: number
}
export interface AdminUserList { items: AdminUserListItem[]; total: number }
export interface AdminUserDetail extends AdminUserListItem {
  correct_rate: number | null
  membership_expires_at: string | null
}
export interface AdminOverview {
  total_users: number
  new_users_today: number
  total_papers: number
  total_attempts: number
  active_members: number | null
}
export interface TimeseriesPoint { day: string; count: number }
export interface AdminTimeseries { users_by_day: TimeseriesPoint[]; papers_by_day: TimeseriesPoint[] }
export interface AdminMembership { user_id: string; expires_at: string | null; active: boolean }
export interface AdminMembershipList { items: AdminMembership[]; total: number }
export interface AdminOrder {
  out_trade_no: string
  user_id: string
  plan_id: string
  amount_cents: number
  status: string
  created_at: string
  paid_at: string | null
}
export interface AdminOrderList { items: AdminOrder[] }
```

- [ ] **Step 4: Create `api/admin.ts`**

```ts
import { apiFetch, payFetch } from '@/api/client'
import type {
  AdminMembership, AdminMembershipList, AdminOrderList, AdminOverview,
  AdminTimeseries, AdminUserDetail, AdminUserList, User,
} from '@/types/api'

const qs = (params: Record<string, string | number | undefined>) => {
  const s = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== '') s.set(k, String(v))
  const out = s.toString()
  return out ? `?${out}` : ''
}

// 用户 / 统计 → 主后端 (/api)
export const listUsers = (q = '', limit = 50, offset = 0) =>
  apiFetch<AdminUserList>(`/admin/users${qs({ q, limit, offset })}`)
export const getUserDetail = (id: string) => apiFetch<AdminUserDetail>(`/admin/users/${id}`)
export const setRole = (id: string, role: 'user' | 'admin') =>
  apiFetch<User>(`/admin/users/${id}/role`, { method: 'POST', body: JSON.stringify({ role }) })
export const resetPassword = (id: string, new_password: string) =>
  apiFetch<User>(`/admin/users/${id}/reset-password`, { method: 'POST', body: JSON.stringify({ new_password }) })
export const banUser = (id: string) => apiFetch<User>(`/admin/users/${id}/ban`, { method: 'POST' })
export const unbanUser = (id: string) => apiFetch<User>(`/admin/users/${id}/unban`, { method: 'POST' })
export const getOverview = () => apiFetch<AdminOverview>('/admin/stats/overview')
export const getTimeseries = (days = 30) => apiFetch<AdminTimeseries>(`/admin/stats/timeseries${qs({ days })}`)

// 会员 / 订单 → 支付服务 (/payapi)
export const listMemberships = (q = '', limit = 50, offset = 0) =>
  payFetch<AdminMembershipList>(`/admin/memberships${qs({ q, limit, offset })}`)
export const grantMembership = (id: string, body: { days?: number; plan_id?: string }) =>
  payFetch<AdminMembership>(`/admin/memberships/${id}/grant`, { method: 'POST', body: JSON.stringify(body) })
export const revokeMembership = (id: string) =>
  payFetch<AdminMembership>(`/admin/memberships/${id}/revoke`, { method: 'POST' })
export const listOrders = (status = '', limit = 50, offset = 0) =>
  payFetch<AdminOrderList>(`/admin/orders${qs({ status, limit, offset })}`)
```

- [ ] **Step 5: Run test**

Run: `cd frontend && npx vitest run src/api/admin.test.ts`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/types/api.ts frontend/src/api/admin.ts frontend/src/api/admin.test.ts
git commit -m "feat(admin): frontend User.role/status types + api/admin client"
```

---

### Task D2: `RequireAdmin` guard + Sidebar entry

**Files:**
- Create: `frontend/src/components/RequireAdmin.tsx`
- Modify: `frontend/src/components/Sidebar.tsx`
- Test: `frontend/src/components/RequireAdmin.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/RequireAdmin.test.tsx`:

```tsx
import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { RequireAdmin } from '@/components/RequireAdmin'

vi.mock('@/hooks/useAuth', () => ({ useAuth: vi.fn() }))
import { useAuth } from '@/hooks/useAuth'

function renderAt(user: unknown) {
  ;(useAuth as unknown as vi.Mock).mockReturnValue({ data: user, isLoading: false })
  return render(
    <MemoryRouter initialEntries={['/admin']}>
      <Routes>
        <Route path="/admin" element={<RequireAdmin><div>ADMIN</div></RequireAdmin>} />
        <Route path="/" element={<div>HOME</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('RequireAdmin', () => {
  it('renders children for admin', () => {
    renderAt({ id: '1', username: 'a', role: 'admin', status: 'active' })
    expect(screen.getByText('ADMIN')).toBeInTheDocument()
  })
  it('redirects non-admin to /', () => {
    renderAt({ id: '2', username: 'u', role: 'user', status: 'active' })
    expect(screen.getByText('HOME')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/RequireAdmin.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Create `RequireAdmin.tsx`** (mirrors `RequireAuth`, uses the same Skeleton loading pattern)

```tsx
import type { ReactNode } from 'react'
import { Navigate } from 'react-router-dom'
import { Skeleton } from '@/components/ui/skeleton'
import { useAuth } from '@/hooks/useAuth'

/** 管理员路由守卫：加载中骨架；非管理员重定向首页。安全由后端 require_admin 兜底。 */
export function RequireAdmin({ children }: { children: ReactNode }) {
  const { data: user, isLoading } = useAuth()
  if (isLoading) {
    return (
      <div className="mx-auto flex max-w-[880px] flex-col gap-4 p-8">
        <Skeleton className="h-10 w-1/3" />
        <Skeleton className="h-40 w-full" />
      </div>
    )
  }
  if (!user || user.role !== 'admin') {
    return <Navigate to="/" replace />
  }
  return children
}
```

- [ ] **Step 4: Add the Sidebar entry (admin-only)** (`frontend/src/components/Sidebar.tsx`)

Import an icon (add `ShieldCheck` to the lucide import). After the `GROUPS.map(...)` block inside `<nav>`, render a conditional group (so the const `GROUPS` stays typed/frozen):

```tsx
        {user?.role === 'admin' && (
          <div className="flex flex-col gap-0.5">
            {collapsed ? (
              <div aria-hidden className="mx-1 my-2.5 border-t border-hairline" />
            ) : (
              <div className="px-3 pb-1 pt-4 text-[10.5px] font-bold tracking-[0.14em] text-quiet">
                管理
              </div>
            )}
            <NavLink
              to="/admin"
              title={collapsed ? '管理后台' : undefined}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-3 rounded-sm px-3 py-[9px] text-[14.5px] transition-colors',
                  collapsed && 'justify-center px-0',
                  isActive ? 'bg-wash text-accent' : 'text-muted-ink hover:bg-tint hover:text-ink',
                )
              }
            >
              <ShieldCheck className="size-[18px] shrink-0" strokeWidth={1.5} />
              {!collapsed && <span className="whitespace-nowrap">管理后台</span>}
            </NavLink>
          </div>
        )}
```

- [ ] **Step 5: Run test**

Run: `cd frontend && npx vitest run src/components/RequireAdmin.test.tsx`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/RequireAdmin.tsx frontend/src/components/RequireAdmin.test.tsx frontend/src/components/Sidebar.tsx
git commit -m "feat(admin): RequireAdmin guard + admin-only sidebar entry"
```

---

### Task D3: Recharts dependency + Admin layout & routes

**Files:**
- Modify: `frontend/package.json`
- Create: `frontend/src/pages/admin/AdminLayout.tsx`
- Modify: `frontend/src/routes.tsx`

- [ ] **Step 1: Install Recharts**

Run: `cd frontend && npm install recharts`
Expected: `recharts` added to `dependencies` in `package.json`.

- [ ] **Step 2: Create `AdminLayout.tsx`** (left sub-nav + `<Outlet/>`), matching current tokens

```tsx
import { NavLink, Outlet } from 'react-router-dom'
import { cn } from '@/lib/utils'

const TABS = [
  { to: '/admin', label: '概览', end: true },
  { to: '/admin/users', label: '用户', end: false },
  { to: '/admin/memberships', label: '会员', end: true },
  { to: '/admin/orders', label: '订单', end: true },
]

export function AdminLayout() {
  return (
    <div className="mx-auto flex w-full max-w-[1040px] gap-8 p-8">
      <nav className="flex w-[140px] shrink-0 flex-col gap-0.5">
        <div className="px-3 pb-2 text-[10.5px] font-bold tracking-[0.14em] text-quiet">管理后台</div>
        {TABS.map((t) => (
          <NavLink
            key={t.to}
            to={t.to}
            end={t.end}
            className={({ isActive }) =>
              cn(
                'rounded-sm px-3 py-2 text-[14px] transition-colors',
                isActive ? 'bg-wash text-accent' : 'text-muted-ink hover:bg-tint hover:text-ink',
              )
            }
          >
            {t.label}
          </NavLink>
        ))}
      </nav>
      <div className="min-w-0 flex-1">
        <Outlet />
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Wire routes** (`frontend/src/routes.tsx`)

Add imports:

```tsx
import { RequireAdmin } from '@/components/RequireAdmin'
import { AdminLayout } from '@/pages/admin/AdminLayout'
import { AdminOverviewPage } from '@/pages/admin/AdminOverviewPage'
import { AdminUsersPage } from '@/pages/admin/AdminUsersPage'
import { AdminUserDetailPage } from '@/pages/admin/AdminUserDetailPage'
import { AdminMembershipsPage } from '@/pages/admin/AdminMembershipsPage'
import { AdminOrdersPage } from '@/pages/admin/AdminOrdersPage'
```

Inside the protected block (the `<Route element={<RequireAuth><AppLayout/></RequireAuth>}>` group), add:

```tsx
        <Route
          path="/admin"
          element={
            <RequireAdmin>
              <AdminLayout />
            </RequireAdmin>
          }
        >
          <Route index element={<AdminOverviewPage />} />
          <Route path="users" element={<AdminUsersPage />} />
          <Route path="users/:userId" element={<AdminUserDetailPage />} />
          <Route path="memberships" element={<AdminMembershipsPage />} />
          <Route path="orders" element={<AdminOrdersPage />} />
        </Route>
```

- [ ] **Step 4: Create page stubs so the app compiles** (each file exports the named component returning a placeholder; fleshed out in D4–D5)

`AdminOverviewPage.tsx`, `AdminUsersPage.tsx`, `AdminUserDetailPage.tsx`, `AdminMembershipsPage.tsx`, `AdminOrdersPage.tsx` — each:

```tsx
export function AdminXxxPage() {
  return <div className="text-[14px] text-muted-ink">TODO</div>
}
```

(Use the correct component name per file.)

- [ ] **Step 5: Verify the app builds**

Run: `cd frontend && npx tsc -p tsconfig.app.json --noEmit`
Expected: no type errors.

- [ ] **Step 6: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/pages/admin frontend/src/routes.tsx
git commit -m "feat(admin): recharts dep + admin layout, routes, page stubs"
```

---

### Task D4: Overview page (metric cards + charts) & Users page

**Files:**
- Modify: `frontend/src/pages/admin/AdminOverviewPage.tsx`, `AdminUsersPage.tsx`, `AdminUserDetailPage.tsx`

- [ ] **Step 1: Overview page** — metric cards + two line charts

```tsx
import { useQuery } from '@tanstack/react-query'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import { getOverview, getTimeseries } from '@/api/admin'

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-md border border-hairline bg-wash/40 px-4 py-3">
      <div className="text-[12px] text-quiet">{label}</div>
      <div className="mt-1 text-[22px] text-ink [font-family:var(--font-display)]">{value}</div>
    </div>
  )
}

export function AdminOverviewPage() {
  const overview = useQuery({ queryKey: ['admin', 'overview'], queryFn: getOverview })
  const series = useQuery({ queryKey: ['admin', 'timeseries'], queryFn: () => getTimeseries(30) })
  const o = overview.data
  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-[20px] text-ink [font-family:var(--font-display)]">概览</h1>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Metric label="总用户" value={o?.total_users ?? '—'} />
        <Metric label="今日新增" value={o?.new_users_today ?? '—'} />
        <Metric label="活跃会员" value={o?.active_members ?? '暂不可用'} />
        <Metric label="试卷总数" value={o?.total_papers ?? '—'} />
      </div>
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {(['users_by_day', 'papers_by_day'] as const).map((key) => (
          <div key={key} className="rounded-md border border-hairline p-4">
            <div className="mb-2 text-[13px] text-muted-ink">
              {key === 'users_by_day' ? '每日新增用户' : '每日生成试卷'}
            </div>
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={series.data?.[key] ?? []}>
                <XAxis dataKey="day" tick={{ fontSize: 11 }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 11 }} width={28} />
                <Tooltip />
                <Line type="monotone" dataKey="count" stroke="var(--color-accent, #1e3a5f)" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        ))}
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Users list page** — search + table + row actions with confirm dialog

```tsx
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { listUsers } from '@/api/admin'
import { Input } from '@/components/ui/input'

export function AdminUsersPage() {
  const [q, setQ] = useState('')
  const users = useQuery({ queryKey: ['admin', 'users', q], queryFn: () => listUsers(q) })
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-[20px] text-ink [font-family:var(--font-display)]">用户</h1>
      <Input placeholder="搜索用户名…" value={q} onChange={(e) => setQ(e.target.value)} className="max-w-[280px]" />
      <div className="overflow-hidden rounded-md border border-hairline">
        <table className="w-full text-[13px]">
          <thead className="bg-wash/60 text-left text-muted-ink">
            <tr>
              <th className="px-3 py-2">用户名</th><th className="px-3 py-2">注册</th>
              <th className="px-3 py-2">角色</th><th className="px-3 py-2">状态</th>
              <th className="px-3 py-2">试卷</th><th className="px-3 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {(users.data?.items ?? []).map((u) => (
              <tr key={u.id} className="border-t border-hairline hover:bg-tint/40">
                <td className="px-3 py-2 text-ink">{u.username}</td>
                <td className="px-3 py-2 text-muted-ink">{u.created_at.slice(0, 10)}</td>
                <td className="px-3 py-2">{u.role === 'admin' ? '管理员' : '用户'}</td>
                <td className="px-3 py-2">{u.status === 'banned' ? '已封禁' : '正常'}</td>
                <td className="px-3 py-2 text-muted-ink">{u.paper_count}</td>
                <td className="px-3 py-2 text-right">
                  <Link to={`/admin/users/${u.id}`} className="text-accent hover:underline">详情</Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
```

- [ ] **Step 3: User detail page** — info + actions (ban/unban, reset password, set role) with confirm dialogs and mutations

Implement `AdminUserDetailPage` using `useParams`, `getUserDetail`, and mutations `banUser`/`unbanUser`/`resetPassword`/`setRole`; each destructive action wrapped in the existing `components/ui/dialog` for confirmation; on success `queryClient.invalidateQueries({ queryKey: ['admin'] })` and `toast.success(...)` via sonner. (Reuse the dialog + toast patterns from `MembershipPage`/`UpgradeDialog`.)

- [ ] **Step 4: Verify build**

Run: `cd frontend && npx tsc -p tsconfig.app.json --noEmit`
Expected: no type errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/admin/
git commit -m "feat(admin): overview dashboard + users list/detail pages"
```

---

### Task D5: Memberships & Orders pages

**Files:**
- Modify: `frontend/src/pages/admin/AdminMembershipsPage.tsx`, `AdminOrdersPage.tsx`

- [ ] **Step 1: Memberships page** — list + grant (N days) / revoke with confirm

Implement with `listMemberships`, `grantMembership`, `revokeMembership`; a small "开通天数" input + button per row (or a dialog); invalidate `['admin','memberships']` on success; sonner toasts. Table styled like the users table (`rounded-md border border-hairline`, header `bg-wash/60`).

- [ ] **Step 2: Orders page** — read-only table + status filter

Implement with `listOrders(status)`; a status `<select>` (CREATED/PAID/EXPIRED/CLOSED/全部); amount rendered as `¥{(amount_cents/100).toFixed(2)}`; columns 订单号/用户/套餐/金额/状态/创建时间.

- [ ] **Step 3: Verify build + run full frontend tests**

Run: `cd frontend && npx tsc -p tsconfig.app.json --noEmit && npx vitest run`
Expected: no type errors; all tests PASS.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/admin/
git commit -m "feat(admin): memberships management + orders list pages"
```

---

## Phase E — Docs sync & full verification

### Task E1: Update Spec C (revoke "no permission system") + cross-references

**Files:**
- Modify: `docs/backend-design.md`
- Modify: `docs/frontend-design.md`

- [ ] **Step 1: Edit `docs/backend-design.md` §12**

Remove the line `- ❌ 不实现权限系统（用户之间无差异，除资源归属）` and add a note: `- 权限系统：见 Spec G（`docs/admin-design.md`）——已引入 users.role + 管理后台，撤销原"不实现权限系统"决策。`
In the revocation table (the section listing revoked Spec A/B decisions), add a row noting Spec G revokes §12's no-permission-system stance.

- [ ] **Step 2: Cross-reference in `docs/frontend-design.md`**

In the routing/auth section, add a one-line pointer: `管理后台路由 /admin 与 RequireAdmin 守卫详见 Spec G（docs/admin-design.md）。`

- [ ] **Step 3: Commit**

```bash
git add docs/backend-design.md docs/frontend-design.md
git commit -m "docs: revoke Spec C no-permission-system; cross-reference Spec G"
```

---

### Task E2: Full backend + payment test sweep

- [ ] **Step 1: Backend suite**

Run: `PYTHONIOENCODING=utf-8 python -m pytest tests/ -v`
Expected: all PASS (no regressions in existing ai_engine/ingestion tests).

- [ ] **Step 2: Payment suite**

Run: `PYTHONIOENCODING=utf-8 python -m pytest payment/tests -v`
Expected: all PASS.

- [ ] **Step 3: Frontend tests + typecheck**

Run: `cd frontend && npx vitest run && npx tsc -p tsconfig.app.json --noEmit`
Expected: all PASS; no type errors.

- [ ] **Step 4: Manual smoke (optional but recommended)**

Bootstrap an admin and click through:
```bash
PYTHONIOENCODING=utf-8 python -m backend.cli create-user --username admin1 --password secret1
PYTHONIOENCODING=utf-8 python -m backend.cli promote-admin --username admin1
```
Start backend (`python -m backend.cli serve`), payment (`uvicorn payment.app.main:app --port 8001`), and frontend (`npm run dev`); log in as `admin1`, confirm the 管理后台 entry shows, `/admin` loads, users list works, grant membership reflects on the user's membership.

- [ ] **Step 5: Final commit (if any doc/tweak remains)**

```bash
git add -A
git commit -m "chore(admin): finalize admin back-office"
```

---

## Self-Review Notes (already applied)

- **Spec coverage:** role+status migrations (§2) → A1/A2; AuthorizationError (§3.1) → A3; require_admin + banned (§3.2/3.3) → A4; CLI (§6) → A5; `/api/admin/users*` (§4.1) → B4; `/api/admin/stats/*` (§4.2) → B5; `/me` role (§4.3) → A1/A4; payment require_admin (§5.1) → C1; memberships/orders + extend_membership (§5.2/5.3) → C2; cross-service assembly (§5.4) → B4/C3; frontend types/guard/routes/pages/charts (§7) → D1–D5; tests (§8) → tests in every task; docs (§0.3) → E1.
- **Placeholders:** page bodies for detail/memberships/orders (D4 step 3, D5) describe exact APIs, tokens, and patterns to reuse rather than full JSX for every row — acceptable as they're mechanical compositions of already-shown pieces (`useQuery`/mutation + the shown table markup). All backend/payment code is complete.
- **Type consistency:** `set_user_role`/`set_user_status`/`update_password_hash`/`delete_sessions_by_user`/`list_users`/`count_users`/`user_correct_rate`/`admin_counts`/`users_created_by_day`/`papers_created_by_day` used consistently across tasks; `extend_membership(user_id, days, now=None)` signature stable; frontend `api/admin.ts` names match page usage.
- **Cross-service caveat:** B4 ships `_fetch_membership_expiry(user_id)` returning None (tests pass with no payment); C3 upgrades it to `(user_id, cookie)` with a matching test — sequencing is intentional and noted.
