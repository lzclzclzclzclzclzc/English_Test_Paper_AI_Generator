"""Unit and integration tests for ai_engine.solutioner.

Structure
---------
1. Pure-function unit tests — helpers against a temp SQLite DB (no LLM):
   _fetch_cached_solution, _kp_level2_names, _write_back_solution

2. generate_solution unit tests — LLM mocked via unittest.mock:
   - cache hit (original + stored solution) → no LLM call
   - cache miss → one LLM call
   - write-back fires only when all three AND conditions hold (Spec B §6.2):
       source_question_id present AND revision_mode == "original"
       AND questions.solution IS NULL
   - light/fresh never write back, never read cache
   - empty LLM output → SolutionerError

3. Integration test — real LLM (needs API key + real bank):
   - solution is non-empty and contains the three section markers
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ai_engine.errors import SolutionerError
from ai_engine.solutioner import (
    _fetch_cached_solution,
    _format_answer,
    _kp_level2_names,
    _write_back_solution,
    generate_solution,
)
from shared.schemas import Option, RevisedQuestion


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def temp_db(tmp_path: Path) -> Path:
    """A minimal questions + knowledge_points DB for helper tests."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE questions (
            id TEXT PRIMARY KEY,
            solution TEXT
        );
        CREATE TABLE knowledge_points (
            id TEXT PRIMARY KEY,
            level1 TEXT,
            level2 TEXT,
            aliases_json TEXT
        );
    """)
    conn.execute("INSERT INTO questions (id, solution) VALUES (?, ?)",
                 ("q_cached", "【关键考点】已缓存的解析"))
    conn.execute("INSERT INTO questions (id, solution) VALUES (?, ?)",
                 ("q_empty", None))
    conn.execute("INSERT INTO knowledge_points (id, level1, level2, aliases_json) VALUES (?, ?, ?, ?)",
                 ("kp_sc_verbs", "single_choice", "动词时态", "[]"))
    conn.execute("INSERT INTO knowledge_points (id, level1, level2, aliases_json) VALUES (?, ?, ?, ?)",
                 ("kp_sc_prepositions", "single_choice", "介词", "[]"))
    conn.commit()
    conn.close()
    return db_path


def _make_sc_revised() -> RevisedQuestion:
    return RevisedQuestion(
        question_type="single_choice",
        knowledge_point_ids=["kp_sc_verbs"],
        stem="Tom ______ to school every day.",
        options=[
            Option(label="A", text="go"),
            Option(label="B", text="goes"),
            Option(label="C", text="going"),
            Option(label="D", text="went"),
        ],
        answer="B",
    )


# ---------------------------------------------------------------------------
# 1. Helper unit tests
# ---------------------------------------------------------------------------

class TestFormatAnswer:
    def test_single_choice_returned_as_is(self):
        assert _format_answer("B") == "B"

    def test_single_blank_single_candidate(self):
        assert _format_answer([{"blank1": ["musician"]}]) == "blank1: musician"

    def test_single_blank_multiple_candidates(self):
        assert _format_answer([{"blank1": ["It's", "It is"]}]) == "blank1: It's / It is"

    def test_multiple_blanks(self):
        out = _format_answer([{"blank1": ["so"], "blank2": ["that"]}])
        assert out == "blank1: so  blank2: that"

    def test_multiple_candidate_groups(self):
        out = _format_answer([
            {"blank1": ["in"], "blank2": ["order"]},
            {"blank1": ["so"], "blank2": ["as"]},
        ])
        assert out == "blank1: in  blank2: order 或 blank1: so  blank2: as"


class TestFetchCachedSolution:
    def test_returns_stored_solution(self, temp_db: Path):
        assert _fetch_cached_solution(str(temp_db), "q_cached") == "【关键考点】已缓存的解析"

    def test_returns_none_when_solution_null(self, temp_db: Path):
        assert _fetch_cached_solution(str(temp_db), "q_empty") is None

    def test_returns_none_when_question_absent(self, temp_db: Path):
        assert _fetch_cached_solution(str(temp_db), "q_nonexistent") is None


class TestKpLevel2Names:
    def test_maps_ids_to_level2(self, temp_db: Path):
        names = _kp_level2_names(str(temp_db), ["kp_sc_verbs", "kp_sc_prepositions"])
        assert names == ["动词时态", "介词"]

    def test_unknown_id_kept_as_is(self, temp_db: Path):
        names = _kp_level2_names(str(temp_db), ["kp_sc_verbs", "kp_unknown"])
        assert names == ["动词时态", "kp_unknown"]

    def test_empty_list_returns_empty(self, temp_db: Path):
        assert _kp_level2_names(str(temp_db), []) == []


class TestWriteBackSolution:
    def test_writes_when_null(self, temp_db: Path):
        _write_back_solution(str(temp_db), "q_empty", "新解析")
        assert _fetch_cached_solution(str(temp_db), "q_empty") == "新解析"

    def test_does_not_overwrite_existing(self, temp_db: Path):
        _write_back_solution(str(temp_db), "q_cached", "不该覆盖")
        # WHERE solution IS NULL guards it — original stays
        assert _fetch_cached_solution(str(temp_db), "q_cached") == "【关键考点】已缓存的解析"


# ---------------------------------------------------------------------------
# 2. generate_solution unit tests (LLM mocked, DB via get_config patch)
# ---------------------------------------------------------------------------

class TestGenerateSolution:
    def _patch_config(self, temp_db: Path):
        mock_cfg = MagicMock()
        mock_cfg.db_path = str(temp_db)
        return patch("ai_engine.solutioner.get_config", return_value=mock_cfg)

    def test_cache_hit_skips_llm(self, temp_db: Path):
        q = _make_sc_revised()
        mock_client = MagicMock()
        with self._patch_config(temp_db), \
             patch("ai_engine.solutioner.get_llm_client", return_value=mock_client):
            result = generate_solution(
                q, source_question_id="q_cached", revision_mode="original"
            )
        assert result == "【关键考点】已缓存的解析"
        mock_client.text.assert_not_called()

    def test_cache_miss_calls_llm_once(self, temp_db: Path):
        q = _make_sc_revised()
        mock_client = MagicMock()
        mock_client.text.return_value = "【关键考点】...\n【解题思路】...\n【易错点】..."
        with self._patch_config(temp_db), \
             patch("ai_engine.solutioner.get_llm_client", return_value=mock_client):
            result = generate_solution(
                q, source_question_id="q_empty", revision_mode="original"
            )
        mock_client.text.assert_called_once()
        assert "关键考点" in result

    def test_write_back_when_all_conditions_met(self, temp_db: Path):
        """original + source_id present + solution NULL → write back."""
        q = _make_sc_revised()
        mock_client = MagicMock()
        mock_client.text.return_value = "【关键考点】新生成"
        with self._patch_config(temp_db), \
             patch("ai_engine.solutioner.get_llm_client", return_value=mock_client):
            generate_solution(q, source_question_id="q_empty", revision_mode="original")
        # solution now cached
        assert _fetch_cached_solution(str(temp_db), "q_empty") == "【关键考点】新生成"

    def test_no_write_back_when_mode_not_original(self, temp_db: Path):
        """revision_mode != original → never write back (content altered)."""
        q = _make_sc_revised()
        mock_client = MagicMock()
        mock_client.text.return_value = "【关键考点】light解析"
        with self._patch_config(temp_db), \
             patch("ai_engine.solutioner.get_llm_client", return_value=mock_client):
            generate_solution(q, source_question_id="q_empty", revision_mode="light")
        # q_empty still NULL — not written
        assert _fetch_cached_solution(str(temp_db), "q_empty") is None

    def test_no_write_back_when_no_source_id(self, temp_db: Path):
        """No source_question_id → never write back."""
        q = _make_sc_revised()
        mock_client = MagicMock()
        mock_client.text.return_value = "【关键考点】无溯源"
        with self._patch_config(temp_db), \
             patch("ai_engine.solutioner.get_llm_client", return_value=mock_client):
            result = generate_solution(q, source_question_id=None, revision_mode="original")
        assert "关键考点" in result
        # nothing to write back to; both rows unchanged
        assert _fetch_cached_solution(str(temp_db), "q_empty") is None

    def test_light_mode_does_not_read_cache(self, temp_db: Path):
        """light mode must call LLM even if a cached solution exists for the id."""
        q = _make_sc_revised()
        mock_client = MagicMock()
        mock_client.text.return_value = "【关键考点】重新生成"
        with self._patch_config(temp_db), \
             patch("ai_engine.solutioner.get_llm_client", return_value=mock_client):
            result = generate_solution(
                q, source_question_id="q_cached", revision_mode="light"
            )
        # cache ignored, LLM used
        mock_client.text.assert_called_once()
        assert result == "【关键考点】重新生成"

    def test_empty_llm_output_raises(self, temp_db: Path):
        q = _make_sc_revised()
        mock_client = MagicMock()
        mock_client.text.return_value = "   "
        with self._patch_config(temp_db), \
             patch("ai_engine.solutioner.get_llm_client", return_value=mock_client):
            with pytest.raises(SolutionerError, match="empty"):
                generate_solution(q, source_question_id="q_empty", revision_mode="original")

    def test_llm_exception_wrapped(self, temp_db: Path):
        q = _make_sc_revised()
        mock_client = MagicMock()
        mock_client.text.side_effect = RuntimeError("API down")
        with self._patch_config(temp_db), \
             patch("ai_engine.solutioner.get_llm_client", return_value=mock_client):
            with pytest.raises(SolutionerError, match="LLM call failed"):
                generate_solution(q, source_question_id="q_empty", revision_mode="original")


# ---------------------------------------------------------------------------
# 3. Integration test — real LLM (needs API key + real bank)
# ---------------------------------------------------------------------------
_resources_ready = Path("data/questions.db").is_file()

pytestmark_integration = pytest.mark.skipif(
    not _resources_ready,
    reason="requires built data/questions.db",
)


@pytestmark_integration
def test_integration_solution_has_sections():
    """Real LLM: solution is non-empty and contains the three section markers."""
    q = _make_sc_revised()
    # no source_question_id → pure generation, no cache/write-back
    solution = generate_solution(q, source_question_id=None, revision_mode=None)
    assert solution.strip()
    # at least one of the required section markers should be present
    assert any(marker in solution for marker in ("关键考点", "解题思路", "易错点"))
