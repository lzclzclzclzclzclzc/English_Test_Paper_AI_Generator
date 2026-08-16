"""Spec H (admin pro) tests: A pagination/sort params, B user recent lists,
C question-bank read-only endpoints, D3 audit log, D4 system health."""

from __future__ import annotations

import json
import shutil
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

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
    storage.set_bank_db_path(None)
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


def _seed_paper(user_id, paper_id, title, days_ago, n_items=3):
    """Minimal papers row: payload_json only needs {"items": [...]} for the
    admin question_count rollup."""
    ts = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()
    with storage.connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO papers"
            " (paper_id, user_id, title, generated_at, payload_json)"
            " VALUES (?, ?, ?, ?, ?)",
            (paper_id, user_id, title, ts, json.dumps({"items": [{}] * n_items})),
        )


def _seed_attempt(user_id, paper_id, days_ago, correct_flags):
    from backend.schemas import StoredAttempt, StoredAttemptItem

    storage.write_attempt(
        StoredAttempt(
            user_id=user_id,
            paper_id=paper_id,
            answered_at=datetime.now(timezone.utc) - timedelta(days=days_ago),
            items=[
                StoredAttemptItem(
                    index=i + 1,
                    source_question_id=f"q_{i:05d}",
                    knowledge_point_ids=["kp_a"],
                    question_type="single_choice",
                    is_correct=ok,
                )
                for i, ok in enumerate(correct_flags)
            ],
        )
    )


# ---- memberships aggregation: never surface locally-deleted users ----


def _fake_payment_memberships(items):
    """Monkeypatch factory: /payapi/admin/memberships returns `items`;
    revenue probe still answers so stats_overview stays green."""

    def fake(path, cookie, params=None):
        if path == "/payapi/admin/memberships":
            return {"items": items, "total": len(items)}
        if path == "/payapi/admin/stats/revenue":
            return {"total_cents": 0, "revenue_by_day": [], "by_plan": []}
        raise AssertionError(f"unexpected payment call: {path}")

    return fake


def test_memberships_list_excludes_deleted_users(client, monkeypatch):
    boss = _mk(client, "boss", admin=True)
    alive = _mk(client, "alive")
    _as(client, boss)
    monkeypatch.setattr(
        "backend.api.admin._payment_get_json",
        _fake_payment_memberships(
            [
                {"user_id": alive.id, "username": None, "expires_at": "2099-01-01T00:00:00Z", "active": True},
                # ghost membership: user_id resolves to no local user
                {"user_id": "ghost-id", "username": None, "expires_at": "2099-01-01T00:00:00Z", "active": True},
            ]
        ),
    )

    r = client.get("/api/admin/memberships")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    assert [i["user_id"] for i in data["items"]] == [alive.id]
    assert data["items"][0]["username"] == "alive"


def test_overview_active_members_excludes_deleted_users(client, monkeypatch):
    boss = _mk(client, "boss", admin=True)
    alive = _mk(client, "alive")
    _as(client, boss)
    monkeypatch.setattr(
        "backend.api.admin._payment_get_json",
        _fake_payment_memberships(
            [
                {"user_id": alive.id, "username": None, "expires_at": "2099-01-01T00:00:00Z", "active": True},
                {"user_id": alive.id, "username": None, "expires_at": "2000-01-01T00:00:00Z", "active": False},
                {"user_id": "ghost-id", "username": None, "expires_at": "2099-01-01T00:00:00Z", "active": True},
            ]
        ),
    )

    r = client.get("/api/admin/stats/overview")
    assert r.status_code == 200
    assert r.json()["active_members"] == 1  # ghost's active membership not counted


# ---- A: users list sort / status filter ----


def test_users_list_status_filter_and_sort(client):
    boss = _mk(client, "boss", admin=True)
    alice = _mk(client, "alice")
    bob = _mk(client, "bob")
    storage.set_user_status(bob.id, "banned")
    # alice answered one paper → attempt_count sorts her first
    _seed_paper(alice.id, "p_a1", "卷A", days_ago=1, n_items=2)
    _seed_attempt(alice.id, "p_a1", days_ago=1, correct_flags=[True, False])
    _as(client, boss)

    r = client.get("/api/admin/users?status=banned")
    assert r.status_code == 200
    assert r.json()["total"] == 1
    assert r.json()["items"][0]["username"] == "bob"

    r2 = client.get("/api/admin/users?sort=attempt_count")
    items = r2.json()["items"]
    assert items[0]["username"] == "alice"
    assert items[0]["attempt_count"] == 1
    assert [i["username"] for i in items[1:]] == ["bob", "boss"]  # 0-attempt tie → newest first

    # attempt_count annotation drives the detail-page linking
    r3 = client.get("/api/admin/users?q=alice")
    assert r3.json()["items"][0]["attempt_count"] == 1


# ---- guards: every new Spec H endpoint rejects non-admins ----


def test_spec_h_new_endpoints_require_admin(client):
    normie = _mk(client, "normie")
    _as(client, normie)
    assert client.get("/api/admin/questionbank/stats").status_code == 403
    assert client.get("/api/admin/questionbank/questions").status_code == 403
    assert client.get(f"/api/admin/users/{normie.id}/papers").status_code == 403
    assert client.get(f"/api/admin/users/{normie.id}/attempts").status_code == 403
    assert client.get("/api/admin/audit").status_code == 403
    assert client.get("/api/admin/system/health").status_code == 403


# ---- B: user detail recent papers / attempts ----


def test_user_recent_papers_ordering_and_counts(client):
    boss = _mk(client, "boss", admin=True)
    u = _mk(client, "stuart")
    _seed_paper(u.id, "p_old", "旧卷", days_ago=5, n_items=3)
    _seed_paper(u.id, "p_new", "新卷", days_ago=1, n_items=5)
    _as(client, boss)

    r = client.get(f"/api/admin/users/{u.id}/papers")
    assert r.status_code == 200
    items = r.json()["items"]
    assert [i["id"] for i in items] == ["p_new", "p_old"]  # newest first
    assert items[0]["question_count"] == 5
    assert items[0]["title"] == "新卷"


def test_user_recent_attempts_rollup(client):
    boss = _mk(client, "boss", admin=True)
    u = _mk(client, "stuart")
    _seed_paper(u.id, "p_old", "旧卷", days_ago=5)
    _seed_paper(u.id, "p_new", "新卷", days_ago=1)
    _seed_attempt(u.id, "p_old", days_ago=4, correct_flags=[True, False])
    _seed_attempt(u.id, "p_new", days_ago=0, correct_flags=[True, True, True, False])
    _as(client, boss)

    r = client.get(f"/api/admin/users/{u.id}/attempts")
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 2
    assert items[0]["paper_title"] == "新卷"  # answered most recently
    assert items[0]["item_total"] == 4
    assert items[0]["item_correct"] == 3
    assert items[0]["correct_rate"] == 0.75
    assert items[1]["paper_title"] == "旧卷"


def test_user_recent_lists_404_for_missing_user(client):
    boss = _mk(client, "boss", admin=True)
    _as(client, boss)
    assert client.get("/api/admin/users/ghost/papers").status_code == 404
    assert client.get("/api/admin/users/ghost/attempts").status_code == 404


# ---- C: question bank stats / search (real-bank-copy, skip without artifact) ----


def _use_real_bank_copy(tmp_path):
    path = Path("data/questions.db")
    if not path.exists():
        pytest.skip("real question-bank artifact is not installed")
    try:
        with sqlite3.connect(path) as conn:
            if conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0] == 0:
                pytest.skip("real question-bank artifact is empty")
    except sqlite3.DatabaseError:
        pytest.skip("real question-bank artifact is not installed")
    db_copy = tmp_path / "questions-copy.db"
    shutil.copyfile(path, db_copy)
    storage.set_bank_db_path(db_copy)
    return db_copy


def test_questionbank_stats_groups_sum_to_total(client, tmp_path):
    boss = _mk(client, "boss", admin=True)
    _as(client, boss)
    db_copy = _use_real_bank_copy(tmp_path)
    before = db_copy.read_bytes()

    r = client.get("/api/admin/questionbank/stats")
    assert r.status_code == 200
    stats = r.json()
    assert stats["total"] > 0
    assert sum(t["count"] for t in stats["by_type"]) == stats["total"]
    assert stats["by_knowledge_point"] and stats["by_chapter"]
    # read-only: file bytes untouched
    assert db_copy.read_bytes() == before


def test_questionbank_search_filters_pagination_and_stem_match(client, tmp_path):
    boss = _mk(client, "boss", admin=True)
    _as(client, boss)
    _use_real_bank_copy(tmp_path)

    # type filter narrows consistently
    r = client.get("/api/admin/questionbank/questions?type=word_form&limit=5")
    assert r.status_code == 200
    page = r.json()
    assert page["total"] >= len(page["items"]) <= 5
    assert all(i["question_type"] == "word_form" for i in page["items"])

    # offset advances within the same filtered set
    r2 = client.get("/api/admin/questionbank/questions?type=word_form&limit=2&offset=2")
    items2 = r2.json()["items"]
    if page["total"] > 4:
        assert items2 and items2[0]["id"] != page["items"][0]["id"]

    # stem fuzzy match: search a fragment of a known question's stem
    q0 = storage.get_question("q_00001")
    fragment = (q0.stem or "")[:6]
    hits = client.get(f"/api/admin/questionbank/questions?q={fragment}&limit=1000").json()
    assert hits["total"] >= 1
    assert any(i["id"] == q0.id for i in hits["items"])

    # items expose the browse-page fields
    sample = page["items"][0]
    assert set(sample) >= {
        "id",
        "question_type",
        "book",
        "chapter_l1",
        "chapter_l2",
        "stem",
        "knowledge_point_ids",
    }


# ---- D3: audit log ----


def test_admin_writes_are_audited(client, monkeypatch):
    import backend.api.admin as admin_mod

    monkeypatch.setattr(
        admin_mod,
        "_payment_post_json",
        lambda path, cookie, json=None: {"user_id": "x", "active": True},
    )
    boss = _mk(client, "boss", admin=True)
    victim = _mk(client, "victim")
    _as(client, boss)

    assert client.post(f"/api/admin/users/{victim.id}/role", json={"role": "admin"}).status_code == 200
    rows = storage.list_admin_audit(action="set_role")[0]
    assert len(rows) == 1
    assert rows[0]["actor_username"] == "boss"
    assert rows[0]["target_username"] == "victim"
    assert rows[0]["detail"] == {"role": "admin"}

    assert client.post(f"/api/admin/users/{victim.id}/ban").status_code == 200
    assert client.post(f"/api/admin/users/{victim.id}/unban").status_code == 200
    assert (
        client.post(
            f"/api/admin/users/{victim.id}/reset-password", json={"new_password": "hushhush1"}
        ).status_code
        == 200
    )
    # plaintext password must never land in the audit detail
    reset_rows = storage.list_admin_audit(action="reset_password")[0]
    assert len(reset_rows) == 1
    assert "hushhush1" not in json.dumps(reset_rows[0]["detail"])

    assert (
        client.post(f"/api/admin/memberships/{victim.id}/grant", json={"days": 30}).status_code == 200
    )
    grant_rows = storage.list_admin_audit(action="grant_membership")[0]
    assert grant_rows[0]["detail"] == {"days": 30}


def test_audit_endpoint_filter_and_pagination(client):
    boss = _mk(client, "boss", admin=True)
    u1 = _mk(client, "u1")
    u2 = _mk(client, "u2")
    _as(client, boss)
    for _ in range(3):
        storage.record_admin_action(boss.id, "ban", u1.id)
    storage.record_admin_action(boss.id, "unban", u2.id)

    r = client.get("/api/admin/audit?action=ban")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 3
    assert all(i["action"] == "ban" for i in data["items"])

    # newest first + pagination slice
    p1 = client.get("/api/admin/audit?limit=2&offset=0").json()
    p2 = client.get("/api/admin/audit?limit=2&offset=2").json()
    assert p1["total"] == p2["total"] == 4
    assert p1["items"][0]["id"] > p1["items"][1]["id"]
    assert {i["id"] for i in p1["items"]}.isdisjoint({i["id"] for i in p2["items"]})


def test_audit_actor_filter(client):
    boss = _mk(client, "boss", admin=True)
    other = _mk(client, "other", admin=True)
    u1 = _mk(client, "u1")
    storage.record_admin_action(boss.id, "ban", u1.id)
    storage.record_admin_action(other.id, "unban", u1.id)
    _as(client, boss)
    r = client.get(f"/api/admin/audit?actor={other.id}")
    assert r.json()["total"] == 1
    assert r.json()["items"][0]["action"] == "unban"


# ---- learner view: single-user analytics ----


def test_user_analytics_scoped_to_single_user(client):
    boss = _mk(client, "boss", admin=True)
    alice = _mk(client, "alice")
    bob = _mk(client, "bob")
    _seed_paper(alice.id, "p_a", "卷A", days_ago=1, n_items=2)
    _seed_paper(bob.id, "p_b", "卷B", days_ago=1, n_items=2)
    # alice: 1 correct + 1 wrong; bob: 2 correct
    _seed_attempt(alice.id, "p_a", days_ago=0, correct_flags=[True, False])
    _seed_attempt(bob.id, "p_b", days_ago=0, correct_flags=[True, True])
    _as(client, boss)

    r = client.get(f"/api/admin/users/{alice.id}/analytics?days=30")
    assert r.status_code == 200
    data = r.json()
    # trend only counts alice's items
    assert sum(d["attempts"] for d in data["attempts_by_day"]) == 2
    day0 = data["attempts_by_day"][-1]
    assert day0["correct_rate"] == 0.5
    # per-type accuracy only from alice's items (1 of 2 correct single_choice)
    by_type = {t["question_type"]: t for t in data["type_accuracy"]}
    assert by_type["single_choice"]["total"] == 2


def test_user_analytics_requires_admin_and_404(client):
    normie = _mk(client, "normie")
    _as(client, normie)
    assert client.get(f"/api/admin/users/{normie.id}/analytics").status_code == 403
    boss = _mk(client, "boss", admin=True)
    _as(client, boss)
    assert client.get("/api/admin/users/ghost/analytics").status_code == 404


# ---- D4: system health ----


def test_system_health(client, monkeypatch):
    import backend.api.admin as admin_mod

    boss = _mk(client, "boss", admin=True)
    _as(client, boss)
    monkeypatch.setattr(admin_mod, "_probe_http", lambda url, timeout=2.0: True)
    monkeypatch.setattr(storage, "questionbank_stats", lambda: {"total": 42})

    r = client.get("/api/admin/system/health")
    assert r.status_code == 200
    body = r.json()
    assert body["payment"] is True
    assert body["llm"] is True
    assert body["question_bank_total"] == 42
    assert body["app_db_size_kb"] > 0
