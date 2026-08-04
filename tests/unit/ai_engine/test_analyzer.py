"""Unit tests for ai_engine.analyzer.

Structure
---------
1. _wilson_lower — pure math on classic inputs (monotonicity, low-sample
   down-weighting, boundary values).
2. build_profile — against a temp SQLite DB (attempts + attempt_items):
   - empty history → empty profile
   - multi-KP expansion (one item counts once per KP)
   - weak_kps ordered ascending by mastery, capped at N
   - dominant_types = most-wrong question types
   - window_days filters by answered_at
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from ai_engine.analyzer import _wilson_lower, build_profile, build_site_profile


# ---------------------------------------------------------------------------
# 1. _wilson_lower — pure math
# ---------------------------------------------------------------------------

class TestWilsonLower:
    def test_zero_total_returns_zero(self):
        assert _wilson_lower(0, 0) == 0.0

    def test_all_correct_high_sample_high_score(self):
        # 20/20 → close to 1 but below it (lower bound)
        score = _wilson_lower(20, 20)
        assert 0.8 < score < 1.0

    def test_all_wrong_returns_low(self):
        assert _wilson_lower(0, 10) < 0.35

    def test_low_sample_downweighted(self):
        """1/1 (100%) should score LOWER than 20/20 (100%) — small samples
        are penalised for uncertainty."""
        assert _wilson_lower(1, 1) < _wilson_lower(20, 20)

    def test_low_sample_wrong_not_rock_bottom(self):
        """1 attempt wrong (0/1) should not be treated as more certain than
        a larger low-accuracy sample."""
        one_wrong = _wilson_lower(0, 1)
        many_low = _wilson_lower(6, 20)  # 30% over 20 attempts
        # 0/1 has huge uncertainty → its lower bound is 0.0
        assert one_wrong == 0.0
        assert many_low > 0.0

    def test_monotonic_in_correct_rate(self):
        assert _wilson_lower(5, 10) < _wilson_lower(8, 10)


# ---------------------------------------------------------------------------
# 2. build_profile — temp DB
# ---------------------------------------------------------------------------

@pytest.fixture
def temp_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE attempts (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            paper_id TEXT,
            answered_at TIMESTAMP
        );
        CREATE TABLE attempt_items (
            attempt_id TEXT,
            source_question_id TEXT,
            question_type TEXT,
            is_correct INTEGER,
            kps_json TEXT
        );
    """)
    conn.commit()
    conn.close()
    return db_path


def _insert_attempt(db_path: Path, attempt_id: str, user_id: str,
                    answered_at: str = "datetime('now')") -> None:
    conn = sqlite3.connect(db_path)
    conn.execute(
        f"INSERT INTO attempts (id, user_id, paper_id, answered_at) "
        f"VALUES (?, ?, 'p1', {answered_at})",
        (attempt_id, user_id),
    )
    conn.commit()
    conn.close()


def _insert_item(db_path: Path, attempt_id: str, qtype: str,
                 is_correct: int, kps: list[str]) -> None:
    import json
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO attempt_items "
        "(attempt_id, source_question_id, question_type, is_correct, kps_json) "
        "VALUES (?, 'q_x', ?, ?, ?)",
        (attempt_id, qtype, is_correct, json.dumps(kps)),
    )
    conn.commit()
    conn.close()


def _patch_config(temp_db: Path):
    """Point analyzer's DB resolution at the temp DB.

    analyzer now resolves the path via storage.get_db_path(), so we set the
    storage override (contextmanager-style) rather than patching get_config."""
    from shared import storage

    class _Ctx:
        def __enter__(self):
            storage.set_db_path(temp_db)
        def __exit__(self, *exc):
            storage.set_db_path(None)

    return _Ctx()


class TestBuildProfileEmpty:
    def test_no_history_returns_empty_profile(self, temp_db: Path):
        with _patch_config(temp_db):
            profile = build_profile("u_nobody")
        assert profile.user_id == "u_nobody"
        assert profile.weak_kps == []
        assert profile.dominant_types == []
        assert profile.total_attempts_considered == 0

    def test_other_user_history_ignored(self, temp_db: Path):
        _insert_attempt(temp_db, "a1", "u_other")
        _insert_item(temp_db, "a1", "single_choice", 0, ["kp_a"])
        with _patch_config(temp_db):
            profile = build_profile("u_me")
        assert profile.total_attempts_considered == 0


class TestBuildProfileBasic:
    def test_total_attempts_counts_items(self, temp_db: Path):
        _insert_attempt(temp_db, "a1", "u1")
        _insert_item(temp_db, "a1", "single_choice", 1, ["kp_a"])
        _insert_item(temp_db, "a1", "single_choice", 0, ["kp_b"])
        with _patch_config(temp_db):
            profile = build_profile("u1")
        assert profile.total_attempts_considered == 2

    def test_multi_kp_expansion(self, temp_db: Path):
        """One item hitting 2 KPs counts once for each KP."""
        _insert_attempt(temp_db, "a1", "u1")
        _insert_item(temp_db, "a1", "single_choice", 0, ["kp_a", "kp_b"])
        with _patch_config(temp_db):
            profile = build_profile("u1")
        kp_ids = {k.knowledge_point_id for k in profile.weak_kps}
        assert kp_ids == {"kp_a", "kp_b"}
        for k in profile.weak_kps:
            assert k.attempts == 1

    def test_weak_kps_ascending_mastery(self, temp_db: Path):
        _insert_attempt(temp_db, "a1", "u1")
        # kp_weak: all wrong; kp_strong: all correct (10 attempts each)
        for i in range(10):
            _insert_item(temp_db, "a1", "single_choice", 0, ["kp_weak"])
            _insert_item(temp_db, "a1", "single_choice", 1, ["kp_strong"])
        with _patch_config(temp_db):
            profile = build_profile("u1")
        masteries = [k.mastery for k in profile.weak_kps]
        assert masteries == sorted(masteries)  # ascending
        assert profile.weak_kps[0].knowledge_point_id == "kp_weak"

    def test_weak_kps_capped_at_8(self, temp_db: Path):
        _insert_attempt(temp_db, "a1", "u1")
        for i in range(12):
            _insert_item(temp_db, "a1", "single_choice", 0, [f"kp_{i:02d}"])
        with _patch_config(temp_db):
            profile = build_profile("u1")
        assert len(profile.weak_kps) == 8

    def test_dominant_types_by_wrong_count(self, temp_db: Path):
        _insert_attempt(temp_db, "a1", "u1")
        # word_form wrong x3, single_choice wrong x1, sentence_rewriting correct
        for _ in range(3):
            _insert_item(temp_db, "a1", "word_form", 0, ["kp_a"])
        _insert_item(temp_db, "a1", "single_choice", 0, ["kp_b"])
        _insert_item(temp_db, "a1", "sentence_rewriting", 1, ["kp_c"])
        with _patch_config(temp_db):
            profile = build_profile("u1")
        assert profile.dominant_types[0] == "word_form"
        assert "sentence_rewriting" not in profile.dominant_types  # no wrongs

    def test_all_correct_still_returns_weak_kps(self, temp_db: Path):
        """Even when everything is correct, weak_kps returns the lowest-mastery
        KPs for 查漏补缺 (Spec B §7.3)."""
        _insert_attempt(temp_db, "a1", "u1")
        _insert_item(temp_db, "a1", "single_choice", 1, ["kp_a"])
        _insert_item(temp_db, "a1", "single_choice", 1, ["kp_b"])
        with _patch_config(temp_db):
            profile = build_profile("u1")
        assert len(profile.weak_kps) == 2
        assert profile.dominant_types == []  # nothing wrong


class TestBuildProfileWindow:
    def test_window_days_filters_old_attempts(self, temp_db: Path):
        # recent attempt (today) and old attempt (100 days ago)
        _insert_attempt(temp_db, "recent", "u1", "datetime('now')")
        _insert_attempt(temp_db, "old", "u1", "datetime('now', '-100 days')")
        _insert_item(temp_db, "recent", "single_choice", 0, ["kp_recent"])
        _insert_item(temp_db, "old", "single_choice", 0, ["kp_old"])

        with _patch_config(temp_db):
            profile = build_profile("u1", window_days=30)

        kp_ids = {k.knowledge_point_id for k in profile.weak_kps}
        assert kp_ids == {"kp_recent"}
        assert profile.total_attempts_considered == 1

    def test_no_window_includes_all(self, temp_db: Path):
        _insert_attempt(temp_db, "recent", "u1", "datetime('now')")
        _insert_attempt(temp_db, "old", "u1", "datetime('now', '-100 days')")
        _insert_item(temp_db, "recent", "single_choice", 0, ["kp_recent"])
        _insert_item(temp_db, "old", "single_choice", 0, ["kp_old"])

        with _patch_config(temp_db):
            profile = build_profile("u1", window_days=None)

        assert profile.total_attempts_considered == 2

    def test_window_days_reflected_in_profile(self, temp_db: Path):
        _insert_attempt(temp_db, "a1", "u1")
        _insert_item(temp_db, "a1", "single_choice", 0, ["kp_a"])
        with _patch_config(temp_db):
            profile = build_profile("u1", window_days=14)
        assert profile.window_days == 14


# ---------------------------------------------------------------------------
# 3. build_site_profile — aggregation across ALL users
# ---------------------------------------------------------------------------

class TestBuildSiteProfile:
    def test_empty_history_returns_empty(self, temp_db: Path):
        with _patch_config(temp_db):
            profile = build_site_profile()
        assert profile.user_id == "__all__"
        assert profile.weak_kps == []
        assert profile.total_attempts_considered == 0

    def test_aggregates_across_users(self, temp_db: Path):
        # two different users; their items must BOTH be counted
        _insert_attempt(temp_db, "a1", "u1")
        _insert_item(temp_db, "a1", "single_choice", 1, ["kp_shared"])
        _insert_attempt(temp_db, "a2", "u2")
        _insert_item(temp_db, "a2", "word_form", 0, ["kp_shared"])
        _insert_item(temp_db, "a2", "word_form", 0, ["kp_only_u2"])

        with _patch_config(temp_db):
            profile = build_site_profile()

        assert profile.user_id == "__all__"
        # 3 items total across both users
        assert profile.total_attempts_considered == 3
        kp_ids = {k.knowledge_point_id for k in profile.weak_kps}
        assert kp_ids == {"kp_shared", "kp_only_u2"}
        # kp_shared: 1 correct / 2 attempts (pooled across users); kp_only_u2: 0/1
        by_id = {k.knowledge_point_id: k for k in profile.weak_kps}
        assert by_id["kp_shared"].attempts == 2

    def test_weak_kps_sorted_ascending(self, temp_db: Path):
        _insert_attempt(temp_db, "a1", "u1")
        # strong KP: many correct; weak KP: many wrong
        for _ in range(10):
            _insert_item(temp_db, "a1", "single_choice", 1, ["kp_strong"])
        for _ in range(10):
            _insert_item(temp_db, "a1", "single_choice", 0, ["kp_weak"])
        with _patch_config(temp_db):
            profile = build_site_profile()
        masteries = [k.mastery for k in profile.weak_kps]
        assert masteries == sorted(masteries)
        assert profile.weak_kps[0].knowledge_point_id == "kp_weak"

    def test_window_filters(self, temp_db: Path):
        _insert_attempt(temp_db, "recent", "u1", "datetime('now')")
        _insert_attempt(temp_db, "old", "u2", "datetime('now', '-100 days')")
        _insert_item(temp_db, "recent", "single_choice", 0, ["kp_recent"])
        _insert_item(temp_db, "old", "single_choice", 0, ["kp_old"])
        with _patch_config(temp_db):
            profile = build_site_profile(window_days=30)
        assert profile.total_attempts_considered == 1
        assert {k.knowledge_point_id for k in profile.weak_kps} == {"kp_recent"}
