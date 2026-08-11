# Split User DB from Question Bank — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Separate user data (`users`/`sessions`/`papers`/`attempts`/`attempt_items`/`study_plans`) into a gitignored `data/app.db`, leaving `data/questions.db` as a read-only, git-tracked question bank — so `git pull` can never overwrite user data and password hashes stop shipping in the repo.

**Architecture:** Two physical SQLite files, two connection helpers. `connect()`/`get_db_path()` route to the **app** DB; new `connect_bank()`/`get_bank_db_path()` route to the **bank** DB. No SQL query JOINs across the two table-groups (verified during design), so no `ATTACH` is needed — each consumer simply opens the right file.

**Tech Stack:** Python 3.11+, SQLite (stdlib `sqlite3`), pydantic-settings, FastAPI, pytest. Windows/bash dev machine — prefix Python with `PYTHONIOENCODING=utf-8`; run tests via `python -m pytest`, never `python file.py`.

**Branch:** `debug` (already checked out; frontend + vector-bank + spec commits already present).

---

## File Structure

Files touched, and their responsibility after the split:

- `shared/config.py` — owns both paths: `db_path` (bank, env `SQLITE_PATH`) + new `app_db_path` (user, env `APP_DB_PATH`).
- `shared/storage.py` — owns the two connection helpers. `connect()`/`get_db_path()`/`set_db_path()` = app; new `connect_bank()`/`get_bank_db_path()`/`set_bank_db_path()` = bank. The 4 bank-reading functions (`list_knowledge_points`, `get_question`, `list_questions`, `write_question_solution`) + helper `_row_to_question` switch to `connect_bank()` and stop calling `init_db()`.
- `backend/api/health.py` — `_readiness_checks()` opens both connections.
- `agent/tools.py` — `get_user_history` reads app (attempts) + bank (kp names); `get_example_questions` reads bank.
- `.gitignore` — add `data/app.db*`.
- `data/questions.db` — user tables + `schema_migrations` dropped, `VACUUM`ed, re-committed clean.
- Tests: `conftest.py`, `test_rate_limit.py`, `test_health.py`, `test_real_database_schema.py` — rewired to set the app path (and bank path where a real bank is needed).
- Docs: `CLAUDE.md`, `docs/backend-design.md` — note the split.

**Important context for the implementer:**
- `get_config()` caches a singleton; tests call `reset_config_cache()` after `monkeypatch.setenv(...)`. Any new env var (`APP_DB_PATH`) must be read inside `get_config()` so the cache reset picks it up.
- `storage.set_db_path(x)` sets a module-global override `DB_PATH_OVERRIDE` that wins over config. We add a parallel `BANK_DB_PATH_OVERRIDE` for the bank.
- `connect()` currently does `PRAGMA foreign_keys = ON` and `mkdir(parents=True)`. `connect_bank()` is read-only in practice but should mirror the structure (minus needing to create tables).

---

## Task 1: Add `app_db_path` to config

**Files:**
- Modify: `shared/config.py:31-35` (field block) and `shared/config.py:55-77` (`get_config` update dict)
- Test: `tests/unit/shared/test_config_app_db.py` (create)

- [ ] **Step 1: Write the failing test**

Create `tests/unit/shared/test_config_app_db.py`:

```python
from __future__ import annotations

from pathlib import Path

from shared.config import get_config, reset_config_cache


def test_app_db_path_defaults_to_data_app_db(monkeypatch):
    monkeypatch.delenv("APP_DB_PATH", raising=False)
    reset_config_cache()
    try:
        assert get_config().app_db_path == Path("data/app.db")
    finally:
        reset_config_cache()


def test_app_db_path_honours_env_override(monkeypatch):
    monkeypatch.setenv("APP_DB_PATH", "/tmp/custom-app.db")
    reset_config_cache()
    try:
        assert get_config().app_db_path == Path("/tmp/custom-app.db")
    finally:
        reset_config_cache()


def test_db_path_still_bank_and_independent(monkeypatch):
    monkeypatch.setenv("SQLITE_PATH", "/tmp/bank.db")
    monkeypatch.setenv("APP_DB_PATH", "/tmp/app.db")
    reset_config_cache()
    try:
        cfg = get_config()
        assert cfg.db_path == Path("/tmp/bank.db")
        assert cfg.app_db_path == Path("/tmp/app.db")
    finally:
        reset_config_cache()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONIOENCODING=utf-8 python -m pytest tests/unit/shared/test_config_app_db.py -v`
Expected: FAIL — `AttributeError: 'AppConfig' object has no attribute 'app_db_path'`

- [ ] **Step 3: Add the field**

In `shared/config.py`, add `app_db_path` right after `db_path` (line 32):

```python
    data_dir: Path = Path("data")
    db_path: Path = Path("data/questions.db")
    app_db_path: Path = Path("data/app.db")
    chroma_path: Path = Path("data/chroma")
```

- [ ] **Step 4: Wire the env override**

In `get_config()`'s update dict, add the `app_db_path` line right after the `db_path` line (currently line 57):

```python
                "db_path": Path(os.getenv("SQLITE_PATH", config.db_path)),
                "app_db_path": Path(os.getenv("APP_DB_PATH", config.app_db_path)),
                "chroma_path": Path(os.getenv("CHROMA_PATH", config.chroma_path)),
```

- [ ] **Step 5: Run test to verify it passes**

Run: `PYTHONIOENCODING=utf-8 python -m pytest tests/unit/shared/test_config_app_db.py -v`
Expected: PASS (3 passed)

- [ ] **Step 6: Commit**

```bash
git add shared/config.py tests/unit/shared/test_config_app_db.py
git commit -m "feat(config): add app_db_path (user DB) separate from db_path (bank)"
```

---

## Task 2: Add bank connection helpers to storage

Adds `connect_bank()` / `get_bank_db_path()` / `set_bank_db_path()` alongside the existing app helpers. `connect()`/`get_db_path()` are **unchanged** in this task (still point at `db_path`) — Task 3 flips them to the app path. This ordering keeps each task's tests green.

**Files:**
- Modify: `shared/storage.py` — add `BANK_DB_PATH_OVERRIDE` near `DB_PATH_OVERRIDE:25`; add helpers near `connect():54`
- Test: `tests/unit/shared/test_storage_connections.py` (create)

- [ ] **Step 1: Write the failing test**

Create `tests/unit/shared/test_storage_connections.py`:

```python
from __future__ import annotations

from pathlib import Path

from shared import storage
from shared.config import reset_config_cache


def test_bank_path_defaults_to_config_db_path(monkeypatch):
    monkeypatch.delenv("SQLITE_PATH", raising=False)
    reset_config_cache()
    storage.set_bank_db_path(None)
    try:
        assert storage.get_bank_db_path() == Path("data/questions.db")
    finally:
        storage.set_bank_db_path(None)
        reset_config_cache()


def test_bank_override_wins(tmp_path):
    bank = tmp_path / "bank.db"
    storage.set_bank_db_path(bank)
    try:
        assert storage.get_bank_db_path() == bank
    finally:
        storage.set_bank_db_path(None)


def test_connect_bank_opens_the_bank_path(tmp_path):
    bank = tmp_path / "bank.db"
    storage.set_bank_db_path(bank)
    try:
        with storage.connect_bank() as conn:
            conn.execute("CREATE TABLE t (x INTEGER)")
            conn.execute("INSERT INTO t VALUES (1)")
        assert bank.exists()
        with storage.connect_bank() as conn:
            assert conn.execute("SELECT x FROM t").fetchone()["x"] == 1
    finally:
        storage.set_bank_db_path(None)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONIOENCODING=utf-8 python -m pytest tests/unit/shared/test_storage_connections.py -v`
Expected: FAIL — `AttributeError: module 'shared.storage' has no attribute 'set_bank_db_path'`

- [ ] **Step 3: Add the bank override global**

In `shared/storage.py`, after the existing `DB_PATH_OVERRIDE: Path | None = None` (line 25), add:

```python
DB_PATH_OVERRIDE: Path | None = None
BANK_DB_PATH_OVERRIDE: Path | None = None
```

- [ ] **Step 4: Add the bank helpers**

In `shared/storage.py`, immediately after `get_chroma_path()` (ends line 51), add:

```python
def set_bank_db_path(path: str | Path | None) -> None:
    global BANK_DB_PATH_OVERRIDE
    BANK_DB_PATH_OVERRIDE = Path(path) if path is not None else None


def get_bank_db_path() -> Path:
    return BANK_DB_PATH_OVERRIDE or get_config().db_path


@contextmanager
def connect_bank() -> Iterator[sqlite3.Connection]:
    """Read-only-in-practice connection to the question bank DB.

    The bank is built offline by ingestion; the app never creates its tables,
    so — unlike connect() — this does not run init_db()/migrations. Callers
    guard with _table_exists() for the not-yet-built case.
    """
    path = get_bank_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `PYTHONIOENCODING=utf-8 python -m pytest tests/unit/shared/test_storage_connections.py -v`
Expected: PASS (3 passed)

- [ ] **Step 6: Commit**

```bash
git add shared/storage.py tests/unit/shared/test_storage_connections.py
git commit -m "feat(storage): add connect_bank/get_bank_db_path/set_bank_db_path helpers"
```

---

## Task 3: Route bank-reading functions to `connect_bank()` and flip `connect()` to the app path

This is the pivot. Two coupled changes that must land together so tests stay coherent:
1. `get_db_path()` now returns the **app** path (`config.app_db_path`).
2. The 4 bank-reading storage functions + `_row_to_question` switch to `connect_bank()` (and drop `init_db()`), so they still hit the bank.

**Files:**
- Modify: `shared/storage.py:46-47` (`get_db_path`), and functions `list_knowledge_points:504`, `get_question:523`, `list_questions:534`, `write_question_solution:575`, `_row_to_question:664`
- Test: `tests/unit/shared/test_storage_split_routing.py` (create)

- [ ] **Step 1: Write the failing test**

Create `tests/unit/shared/test_storage_split_routing.py`:

```python
from __future__ import annotations

import sqlite3

from shared import storage
from shared.config import reset_config_cache


def _make_bank(path):
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE questions (id TEXT PRIMARY KEY, book TEXT, question_type TEXT,
            chapter_l1 TEXT, chapter_l2 TEXT, number INTEGER, stem TEXT,
            options_json TEXT, hint TEXT, original_sentence TEXT, instruction TEXT,
            template TEXT, answer_json TEXT, solution TEXT, source_md TEXT,
            source_line INTEGER, created_at TIMESTAMP, version INTEGER);
        CREATE TABLE knowledge_points (id TEXT PRIMARY KEY, level1 TEXT, level2 TEXT, aliases_json TEXT);
        CREATE TABLE question_knowledge_points (question_id TEXT, knowledge_point_id TEXT);
        INSERT INTO knowledge_points VALUES ('kp1','single_choice','一般现在时','[]');
        INSERT INTO questions VALUES ('q1','b','single_choice','l1','l2',1,'stem',
            NULL,NULL,NULL,NULL,NULL,'"B"',NULL,'m.md',1,'2026-01-01T00:00:00+00:00',1);
        INSERT INTO question_knowledge_points VALUES ('q1','kp1');
        """
    )
    conn.commit()
    conn.close()


def test_bank_reads_hit_bank_not_app(tmp_path, monkeypatch):
    bank = tmp_path / "bank.db"
    app = tmp_path / "app.db"
    _make_bank(bank)
    monkeypatch.setenv("SQLITE_PATH", str(bank))
    monkeypatch.setenv("APP_DB_PATH", str(app))
    reset_config_cache()
    storage.set_db_path(app)
    storage.set_bank_db_path(bank)
    try:
        # question bank reads resolve from the bank file
        assert storage.get_question("q1") is not None
        assert [kp.id for kp in storage.list_knowledge_points()] == ["kp1"]
        assert len(storage.list_questions()) == 1
        # get_db_path() (app) points at the app file, which has NO questions table
        assert storage.get_db_path() == app
    finally:
        storage.set_db_path(None)
        storage.set_bank_db_path(None)
        reset_config_cache()


def test_app_writes_do_not_create_bank_tables(tmp_path, monkeypatch):
    bank = tmp_path / "bank.db"
    app = tmp_path / "app.db"
    _make_bank(bank)
    monkeypatch.setenv("SQLITE_PATH", str(bank))
    monkeypatch.setenv("APP_DB_PATH", str(app))
    monkeypatch.setenv("BCRYPT_ROUNDS", "4")
    reset_config_cache()
    storage.set_db_path(app)
    storage.set_bank_db_path(bank)
    try:
        storage.create_user("alice", "hash")  # writes to app.db, runs init_db()
        with storage.connect() as conn:  # app connection
            names = {r["name"] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
        assert "users" in names
        assert "questions" not in names  # bank tables never created in app.db
    finally:
        storage.set_db_path(None)
        storage.set_bank_db_path(None)
        reset_config_cache()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONIOENCODING=utf-8 python -m pytest tests/unit/shared/test_storage_split_routing.py -v`
Expected: FAIL — `get_question` currently uses `connect()`→app path (no `questions` table), returns `None`; and `get_db_path()` still returns the bank path.

- [ ] **Step 3: Flip `get_db_path()` to the app path**

In `shared/storage.py`, change `get_db_path()` (line 46-47):

```python
def get_db_path() -> Path:
    return DB_PATH_OVERRIDE or get_config().app_db_path
```

- [ ] **Step 4: Route `list_knowledge_points` to the bank**

Replace the body of `list_knowledge_points()` (lines 504-506) — drop `init_db()`, use `connect_bank()`:

```python
def list_knowledge_points() -> list[KnowledgePoint]:
    with connect_bank() as conn:
        if not _table_exists(conn, "knowledge_points"):
            return []
```
(The rest of the function body — the `rows = conn.execute(...)` and the return — stays identical.)

- [ ] **Step 5: Route `get_question` to the bank**

Replace `get_question()` header lines (523-525):

```python
def get_question(question_id: str) -> Question | None:
    with connect_bank() as conn:
        if not _table_exists(conn, "questions"):
            return None
```
(Rest of body unchanged.)

- [ ] **Step 6: Route `list_questions` to the bank**

In `list_questions()`, replace the `init_db()` + `with connect() as conn:` prologue (lines 542-543):

```python
    with connect_bank() as conn:
        if not _table_exists(conn, "questions"):
            return []
```
(Delete the `init_db()` line; rest of body unchanged.)

- [ ] **Step 7: Route `write_question_solution` to the bank**

In `write_question_solution()`, replace the `init_db()` + `with connect() as conn:` prologue (lines 576-577):

```python
def write_question_solution(question_id: str, solution: str) -> bool:
    with connect_bank() as conn:
        if not _table_exists(conn, "questions"):
            return False
```
(Rest of body unchanged. `_row_to_question` at line 664 receives whatever conn its caller passes — now a bank conn — so no edit needed there; verify it uses only the passed `conn`.)

- [ ] **Step 8: Run test to verify it passes**

Run: `PYTHONIOENCODING=utf-8 python -m pytest tests/unit/shared/test_storage_split_routing.py -v`
Expected: PASS (2 passed)

- [ ] **Step 9: Commit**

```bash
git add shared/storage.py tests/unit/shared/test_storage_split_routing.py
git commit -m "refactor(storage): route bank reads to connect_bank, app path for connect()"
```

---

## Task 4: Rewire the readiness check to two connections

**Files:**
- Modify: `backend/api/health.py:32-58` (`_readiness_checks`)
- Test: `tests/integration/backend/test_health.py` — existing `test_readiness_reports_missing_question_bank` and `test_readiness_accepts_real_question_bank_copy` (see Task 7 for the real-copy one; this task fixes the missing-bank one)

- [ ] **Step 1: Update `_readiness_checks` to open both DBs**

Replace `_readiness_checks()` (lines 32-58) with:

```python
def _readiness_checks() -> dict[str, bool]:
    checks = {
        "sqlite": False,
        "core_tables": False,
        "question_bank": False,
        "vector_bank": False,
    }
    try:
        with storage.connect() as app_conn:
            app_conn.execute("SELECT 1").fetchone()
            checks["sqlite"] = True
            checks["core_tables"] = _has_tables(
                app_conn,
                {
                    "users",
                    "sessions",
                    "papers",
                    "attempts",
                    "attempt_items",
                    "schema_migrations",
                },
            )
    except Exception:
        return checks
    try:
        with storage.connect_bank() as bank_conn:
            bank_conn.execute("SELECT 1").fetchone()
            checks["question_bank"] = _has_question_bank(bank_conn)
            checks["vector_bank"] = _has_vector_bank(bank_conn)
    except Exception:
        pass
    return checks
```

- [ ] **Step 2: Verify the existing missing-bank test still holds**

`test_readiness_reports_missing_question_bank` (test_health.py:110) uses the `client` fixture (app DB in tmp, no bank). After Task 7 rewires the fixture, `sqlite`/`core_tables` = True (app DB has user tables via `init_db()` on register — but note this test does NOT register). Confirm current assertions still match; the test expects `question_bank=False`, `vector_bank=False`. The app-side `core_tables`: the fixture calls `init_db()`? It does not automatically. Check: the `client` fixture only creates the app path; `init_db()` runs on first storage write. So `core_tables` may be False here too.

Run: `PYTHONIOENCODING=utf-8 python -m pytest "tests/integration/backend/test_health.py::test_readiness_reports_missing_question_bank" -v`
Expected: currently may FAIL on `core_tables` assertion. If so, fix the test in this step to assert the real post-split shape:

```python
def test_readiness_reports_missing_question_bank(client):
    response = client.get("/api/health/ready")
    body = response.json()

    assert response.status_code == 503
    assert body["status"] == "not_ready"
    assert body["checks"]["sqlite"] is True
    assert body["checks"]["question_bank"] is False
    assert body["checks"]["vector_bank"] is False
```
(Drop the brittle `core_tables` assertion — it depends on whether `init_db()` ran, which is orthogonal to "question bank missing". `sqlite:True` already proves the app DB opened.)

- [ ] **Step 3: Run the missing-bank test**

Run: `PYTHONIOENCODING=utf-8 python -m pytest "tests/integration/backend/test_health.py::test_readiness_reports_missing_question_bank" -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add backend/api/health.py tests/integration/backend/test_health.py
git commit -m "refactor(health): open app + bank connections separately in readiness"
```

---

## Task 5: Rewire agent tools to the correct DBs

**Files:**
- Modify: `agent/tools.py:40-43` (`_connect`), `get_user_history:95-106` (the kp-name lookup), `get_example_questions:138`

- [ ] **Step 1: Write the failing test**

Create `tests/integration/agent/test_tools_db_split.py`:

```python
from __future__ import annotations

import sqlite3

from shared import storage
from shared.config import reset_config_cache
from agent import tools


def _make_bank(path):
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE questions (id TEXT PRIMARY KEY, question_type TEXT, stem TEXT,
            options_json TEXT, hint TEXT, original_sentence TEXT, instruction TEXT,
            template TEXT, answer_json TEXT);
        CREATE TABLE knowledge_points (id TEXT PRIMARY KEY, level1 TEXT, level2 TEXT, aliases_json TEXT);
        CREATE TABLE question_knowledge_points (question_id TEXT, knowledge_point_id TEXT);
        INSERT INTO knowledge_points VALUES ('kp1','single_choice','一般现在时','[]');
        INSERT INTO questions VALUES ('q1','single_choice','stem',NULL,NULL,NULL,NULL,NULL,'"B"');
        INSERT INTO question_knowledge_points VALUES ('q1','kp1');
        """
    )
    conn.commit()
    conn.close()


def test_get_example_questions_reads_bank(tmp_path, monkeypatch):
    bank = tmp_path / "bank.db"
    app = tmp_path / "app.db"
    _make_bank(bank)
    monkeypatch.setenv("SQLITE_PATH", str(bank))
    monkeypatch.setenv("APP_DB_PATH", str(app))
    reset_config_cache()
    storage.set_db_path(app)
    storage.set_bank_db_path(bank)
    try:
        # .func unwraps the @function_tool decorator to call the plain function
        out = tools.get_example_questions.func("kp1", 3)
        assert "q1" in out
    finally:
        storage.set_db_path(None)
        storage.set_bank_db_path(None)
        reset_config_cache()
```

Note: if `@function_tool` does not expose `.func`, call the underlying function via the attribute the `agents` lib provides (check `type(tools.get_example_questions)`); adjust the call site accordingly. If unwrapping is impractical, test `get_example_questions` logic by extracting a plain `_example_questions(kp_id, count)` helper and calling that.

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONIOENCODING=utf-8 python -m pytest tests/integration/agent/test_tools_db_split.py -v`
Expected: FAIL — `get_example_questions` uses `_connect()`→app path, which has no `questions` table.

- [ ] **Step 3: Split the connection helper**

In `agent/tools.py`, replace `_connect()` (lines 40-43):

```python
def _connect_app() -> sqlite3.Connection:
    conn = sqlite3.connect(str(storage.get_db_path()))
    conn.row_factory = sqlite3.Row
    return conn


def _connect_bank() -> sqlite3.Connection:
    conn = sqlite3.connect(str(storage.get_bank_db_path()))
    conn.row_factory = sqlite3.Row
    return conn
```

- [ ] **Step 4: Point `get_user_history`'s two queries at the right DBs**

In `get_user_history`, the attempts query (`conn = _connect()` at line 56) reads user tables → `_connect_app()`. The kp-name lookup (`conn2 = _connect()` at line 95) reads `knowledge_points` → `_connect_bank()`. Change:

```python
    user_id = _require_user_id()
    conn = _connect_app()
```

and:

```python
    # resolve level2 names
    conn2 = _connect_bank()
```

- [ ] **Step 5: Point `get_example_questions` at the bank**

In `get_example_questions`, change `conn = _connect()` (line 138) to:

```python
    conn = _connect_bank()
```

- [ ] **Step 6: Run test to verify it passes**

Run: `PYTHONIOENCODING=utf-8 python -m pytest tests/integration/agent/test_tools_db_split.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add agent/tools.py tests/integration/agent/test_tools_db_split.py
git commit -m "refactor(agent): route example questions + kp names to bank, history to app"
```

---

## Task 6: Rewire mock-backed test fixtures (conftest, rate_limit) to the app path

These fixtures use a mocked AI gateway and never touch a real bank. After the split, `storage.set_db_path()` = app path, so they just need `APP_DB_PATH` instead of `SQLITE_PATH`.

**Files:**
- Modify: `tests/integration/backend/conftest.py:44-46`
- Modify: `tests/integration/backend/test_rate_limit.py:26-28`

- [ ] **Step 1: Update conftest `client` fixture**

In `tests/integration/backend/conftest.py`, replace lines 44-46:

```python
    db_path = tmp_path / "backend-test.db"
    storage.set_db_path(db_path)
    monkeypatch.setenv("APP_DB_PATH", str(db_path))
```

- [ ] **Step 2: Update rate-limit fixture**

In `tests/integration/backend/test_rate_limit.py`, replace lines 26-28:

```python
    db_path = tmp_path / "rate-limit-test.db"
    storage.set_db_path(db_path)
    monkeypatch.setenv("APP_DB_PATH", str(db_path))
```

- [ ] **Step 3: Reset bank override in teardown (both files)**

To avoid cross-test leakage, ensure both fixtures also clear the bank override. In `conftest.py` teardown (after `storage.set_db_path(None)` on line 59) add `storage.set_bank_db_path(None)`. Same in `test_rate_limit.py` teardown (after its `storage.set_db_path(None)` on line 40).

- [ ] **Step 4: Run the mock-backed suites**

Run: `PYTHONIOENCODING=utf-8 python -m pytest tests/integration/backend/test_rate_limit.py tests/integration/backend/test_papers.py tests/integration/backend/test_auth.py -v` (adjust to whichever test files use the `client`/`logged_in_client` fixtures)
Expected: PASS (all green — these never needed the bank; the register→generate→grade flow uses the mocked gateway and the app DB)

- [ ] **Step 5: Commit**

```bash
git add tests/integration/backend/conftest.py tests/integration/backend/test_rate_limit.py
git commit -m "test: point mock-backed fixtures at APP_DB_PATH after DB split"
```

---

## Task 7: Rewire the real-DB tests (bank copy + fresh app)

Both real-DB tests copy the real `questions.db` as the **bank** and need a separate fresh **app** DB for user tables. This also naturally fixes the pre-existing `attempt_count == 1` failure: a fresh app DB starts with 0 attempts, and the test does exactly one grade → 1.

**Files:**
- Modify: `tests/integration/backend/test_real_database_schema.py:38-48` (setup), `:78-88` (verification block reads), `:108` (`attempt_count` assertion)
- Modify: `tests/integration/backend/test_health.py:122-149` (`test_readiness_accepts_real_question_bank_copy`)

- [ ] **Step 1: Update `test_backend_flow` setup to two DBs**

In `test_real_database_schema.py`, replace the setup (lines 43-48):

```python
    app_db = tmp_path / "app.db"
    monkeypatch.setenv("BACKEND_ENV", "test")
    monkeypatch.setenv("BCRYPT_ROUNDS", "4")
    monkeypatch.setenv("SQLITE_PATH", str(db_copy))     # bank = copied real questions.db
    monkeypatch.setenv("APP_DB_PATH", str(app_db))       # user data = fresh temp file
    monkeypatch.setattr(ai_gateway, "generate_paper", _fake_paper)
    reset_config_cache()
    storage.set_db_path(app_db)
    storage.set_bank_db_path(db_copy)
```

- [ ] **Step 2: Split the verification block's reads**

In the same test, the verification block (lines 78-88) currently reads everything from `storage.connect()`. Split it: bank reads (`questions`, `knowledge_points`, `question_knowledge_points`, their columns) from `connect_bank()`; user reads (`attempt_count`, `attempt_items` columns, `users`/`papers`/`schema_migrations` presence) from `connect()`. Replace lines 78-88:

```python
        with storage.connect_bank() as conn:
            question_count = conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
            kp_count = conn.execute("SELECT COUNT(*) FROM knowledge_points").fetchone()[0]
            qkp_count = conn.execute("SELECT COUNT(*) FROM question_knowledge_points").fetchone()[0]
            question_columns = {row["name"] for row in conn.execute("PRAGMA table_info(questions)")}
            kp_columns = {row["name"] for row in conn.execute("PRAGMA table_info(knowledge_points)")}

        with storage.connect() as conn:
            attempt_count = conn.execute("SELECT COUNT(*) FROM attempts").fetchone()[0]
            attempt_item_columns = {row["name"] for row in conn.execute("PRAGMA table_info(attempt_items)")}
            users_table = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'").fetchone()
            papers_table = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='papers'").fetchone()
            migration_count = conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0]
```

- [ ] **Step 3: Keep the `attempt_count == 1` assertion (now correct)**

The assertion at line 108 (`assert attempt_count == 1`) is now correct against a fresh app DB — the test performs exactly one grade. Per the design decision (adopted), keep it as a normal-flow check rather than a hard-coded fixture number: it verifies "after one register→generate→grade, exactly one attempt exists." Leave the assertion as-is; add a clarifying comment above it:

```python
        # fresh app.db + exactly one graded paper in this test → exactly one attempt
        assert attempt_count == 1
```

- [ ] **Step 4: Add teardown for the bank override**

The test's `finally` block (around line 113-115) does `storage.set_db_path(None)` + `reset_config_cache()`. Add `storage.set_bank_db_path(None)` there too.

- [ ] **Step 5: Update `test_readiness_accepts_real_question_bank_copy`**

In `test_health.py`, replace the setup of `test_readiness_accepts_real_question_bank_copy` (lines 127-130) so the bank is the copy and the app is a fresh temp file, and register a user so `core_tables` becomes True:

```python
    app_db = tmp_path / "app.db"
    monkeypatch.setenv("BACKEND_ENV", "test")
    monkeypatch.setenv("BCRYPT_ROUNDS", "4")
    monkeypatch.setenv("SQLITE_PATH", str(db_copy))
    monkeypatch.setenv("APP_DB_PATH", str(app_db))
    reset_config_cache()
    storage.set_db_path(app_db)
    storage.set_bank_db_path(db_copy)
```

Then, inside the `try`, before hitting `/api/health/ready`, initialise the app schema so `core_tables` passes:

```python
        get_config()
        storage.init_db()  # create user tables in the fresh app.db
        with TestClient(create_app(), raise_server_exceptions=False) as real_db_client:
            response = real_db_client.get("/api/health/ready")
```

Keep the existing assertion that all four checks are True. Add `storage.set_bank_db_path(None)` to the `finally` block (after line 148).

- [ ] **Step 6: Run both real-DB tests**

Run: `PYTHONIOENCODING=utf-8 python -m pytest tests/integration/backend/test_real_database_schema.py tests/integration/backend/test_health.py -v`
Expected: PASS (including `test_backend_flow_against_copied_real_question_bank`, previously failing on `attempt_count`)

- [ ] **Step 7: Commit**

```bash
git add tests/integration/backend/test_real_database_schema.py tests/integration/backend/test_health.py
git commit -m "test: rewire real-DB tests to bank-copy + fresh app.db; fix attempt_count"
```

---

## Task 8: Strip user tables from the tracked `questions.db` and gitignore `app.db`

Produces the clean, git-tracked bank and stops user data from ever being tracked.

**Files:**
- Modify: `.gitignore`
- Modify (binary, via SQL): `data/questions.db`
- Create (helper, then delete): a one-off Python snippet run via `python -c`

- [ ] **Step 1: Snapshot current state**

Run:
```bash
PYTHONIOENCODING=utf-8 python -c "import sqlite3; c=sqlite3.connect('data/questions.db'); print(sorted(r[0] for r in c.execute(\"SELECT name FROM sqlite_master WHERE type='table'\")))"
```
Expected: a list containing both bank tables (`questions`, `knowledge_points`, `question_knowledge_points`) and user tables (`users`, `sessions`, `papers`, `attempts`, `attempt_items`, `study_plans`, `schema_migrations`).

- [ ] **Step 2: Back up the current file (safety, not committed)**

Run:
```bash
cp data/questions.db /tmp/questions.db.backup
```

- [ ] **Step 3: Drop user tables + VACUUM**

Run:
```bash
PYTHONIOENCODING=utf-8 python -c "
import sqlite3
c = sqlite3.connect('data/questions.db')
for t in ['sessions','papers','attempt_items','attempts','study_plans','users','schema_migrations']:
    c.execute(f'DROP TABLE IF EXISTS {t}')
c.commit()
c.execute('VACUUM')
c.commit()
print('remaining:', sorted(r[0] for r in c.execute(\"SELECT name FROM sqlite_master WHERE type='table'\")))
c.close()
"
```
Expected: `remaining: ['knowledge_points', 'question_knowledge_points', 'questions']` (plus possibly `sqlite_sequence` — that's fine, it's not user data).

Order note: `sessions`/`papers`/`attempt_items` are dropped before their FK targets (`users`/`attempts`) to respect `REFERENCES`; `DROP TABLE` in SQLite ignores FK by default but this order is safe regardless.

- [ ] **Step 4: Verify no user data remains**

Run:
```bash
PYTHONIOENCODING=utf-8 python -c "
import sqlite3
c=sqlite3.connect('data/questions.db')
for t in ['users','sessions','papers','attempts','attempt_items','study_plans']:
    try:
        c.execute(f'SELECT 1 FROM {t} LIMIT 1'); print('STILL PRESENT:', t)
    except sqlite3.OperationalError:
        pass
print('question count:', c.execute('SELECT COUNT(*) FROM questions').fetchone()[0])
"
```
Expected: no "STILL PRESENT" lines; `question count: 1397`.

- [ ] **Step 5: Add app.db to .gitignore**

In `.gitignore`, under the existing `data/agent_sessions.db*` line, add:

```
data/agent_sessions.db*
data/app.db*
```

- [ ] **Step 6: Verify app.db is ignored**

Run:
```bash
touch data/app.db && git check-ignore data/app.db && rm data/app.db
```
Expected: prints `data/app.db` (meaning it IS ignored).

- [ ] **Step 7: Commit the clean bank + gitignore**

```bash
git add .gitignore data/questions.db
git commit -m "chore(data): strip user tables from tracked questions.db; gitignore app.db

The tracked bank shipped user rows incl. password hashes and forced
git-pull conflicts. Bank now holds only questions/knowledge_points/
question_knowledge_points; user data lives in the gitignored data/app.db."
```

---

## Task 9: Full suite + deploy-check + docs

**Files:**
- Modify: `CLAUDE.md` (data-contract section), `docs/backend-design.md` (storage section)

- [ ] **Step 1: Run the entire test suite**

Run: `PYTHONIOENCODING=utf-8 python -m pytest tests/ -v`
Expected: all green (any pre-existing skips for missing artifacts remain skips, not failures).

- [ ] **Step 2: Run deploy-check with a fresh app.db**

Run:
```bash
rm -f data/app.db
PYTHONIOENCODING=utf-8 python -m backend.cli init-db
BACKEND_ENV=production PYTHONIOENCODING=utf-8 python -m backend.cli deploy-check
```
Expected: `init-db` prints the app.db path; `deploy-check` prints `"status": "ready"` with all four checks true (bank checks read the tracked `questions.db`, app checks read the freshly-created `data/app.db`).

- [ ] **Step 3: Confirm app.db is untracked**

Run: `git status --short data/` and `git ls-files data/ | grep app.db || echo "app.db NOT tracked (good)"`
Expected: `data/app.db` does not appear in tracked files; `questions.db` is clean (no `M`).

- [ ] **Step 4: Update CLAUDE.md**

In `CLAUDE.md`, in the "Data contracts" or "Environment & how to run" section, add a bullet:

```markdown
- **Two SQLite files, split by ownership:** `data/questions.db` is the
  read-only, git-tracked question bank (questions / knowledge_points /
  question_knowledge_points). User data (users / sessions / papers / attempts /
  attempt_items / study_plans / schema_migrations) lives in `data/app.db`,
  which is **gitignored** — created fresh by `init-db` on first run. Bank reads
  go through `storage.connect_bank()` (env `SQLITE_PATH`); user reads through
  `storage.connect()` (env `APP_DB_PATH`). No query JOINs across the two.
```

- [ ] **Step 5: Update docs/backend-design.md**

Add or amend the storage/persistence section of `docs/backend-design.md` to describe the two-file split, the two connection helpers, and the readiness check opening both. (Match the file's existing heading style; keep it to a short paragraph + the table of which tables live where.)

- [ ] **Step 6: Commit docs**

```bash
git add CLAUDE.md docs/backend-design.md
git commit -m "docs: document user-DB / question-bank split"
```

---

## Self-Review Notes

- **Spec coverage:** config (T1), storage connection split (T2-T3), readiness two-conn (T4), agent tools (T5), test rewiring (T6-T7), repo cleanup + gitignore (T8), verification + docs (T9). All spec sections mapped.
- **`attempt_count == 1`:** design adopted "normal-flow check, not hard-coded number" — realised in T7 step 3 by keeping `== 1` with a comment justifying it as the flow's expected result against a fresh app DB (exactly one grade performed).
- **Type/name consistency:** `connect_bank`, `get_bank_db_path`, `set_bank_db_path`, `BANK_DB_PATH_OVERRIDE`, env `APP_DB_PATH`, config `app_db_path` — used identically across T1-T9.
- **Ordering safety:** T2 adds bank helpers without moving `connect()`; T3 flips `get_db_path()` and bank-fn routing together so no intermediate state leaves bank reads pointing at the empty app DB.
- **Open risk flagged in T5:** `@function_tool` unwrapping (`.func`) may differ by `agents` lib version — step includes a fallback (extract a plain helper) if `.func` is unavailable.
