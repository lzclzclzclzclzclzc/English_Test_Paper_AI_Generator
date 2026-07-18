"""Unit and integration tests for ai_engine.parser.

Contract:
- _local_validate filters invalid KP ids, caps total_questions at 30,
  and scales down distributions that exceed total_questions.
- _build_kp_catalog_text formats KP list with aliases.
- _build_prompt assembles system + user prompts with all context.
- parse() end-to-end: natural language → GenerateRequest (integration,
  requires LLM API key + SQLite DB).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from ai_engine.parser import (
    MAX_QUESTIONS,
    _build_kp_catalog_text,
    _build_prompt,
    _load_kp_catalog,
    _local_validate,
    parse,
)
from ai_engine.errors import ParserError
from shared.schemas import (
    GenerateRequest,
    KnowledgePoint,
    KPMastery,
    MasteryProfile,
    WrongItemRef,
)


# ─────────────────────────────────────────────────────────────────────────────
# fixtures
# ─────────────────────────────────────────────────────────────────────────────
@pytest.fixture
def sample_kps() -> list[KnowledgePoint]:
    return [
        KnowledgePoint(id="kp_sc_verbs", level1="single_choice", level2="动词", aliases=["verb"]),
        KnowledgePoint(id="kp_sc_prepositions", level1="single_choice", level2="介词", aliases=[]),
        KnowledgePoint(id="kp_wf_plural", level1="word_form", level2="名词改复数", aliases=[]),
    ]


@pytest.fixture
def tmp_db(tmp_path: Path, sample_kps: list[KnowledgePoint]) -> Path:
    """Create a temporary SQLite DB with sample knowledge points."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE knowledge_points (
            id TEXT PRIMARY KEY,
            level1 TEXT,
            level2 TEXT,
            aliases_json TEXT
        );
    """)
    for kp in sample_kps:
        import json
        conn.execute(
            "INSERT INTO knowledge_points (id, level1, level2, aliases_json) VALUES (?, ?, ?, ?)",
            (kp.id, kp.level1, kp.level2, json.dumps(kp.aliases)),
        )
    conn.commit()
    conn.close()
    return db_path


# ─────────────────────────────────────────────────────────────────────────────
# _load_kp_catalog
# ─────────────────────────────────────────────────────────────────────────────
def test_load_kp_catalog_reads_all_rows(tmp_db: Path, sample_kps: list[KnowledgePoint]) -> None:
    kps = _load_kp_catalog(str(tmp_db))
    assert len(kps) == len(sample_kps)
    ids = {kp.id for kp in kps}
    assert ids == {"kp_sc_verbs", "kp_sc_prepositions", "kp_wf_plural"}


def test_load_kp_catalog_parses_aliases(tmp_db: Path) -> None:
    kps = _load_kp_catalog(str(tmp_db))
    verbs = next(kp for kp in kps if kp.id == "kp_sc_verbs")
    assert verbs.aliases == ["verb"]
    prep = next(kp for kp in kps if kp.id == "kp_sc_prepositions")
    assert prep.aliases == []


# ─────────────────────────────────────────────────────────────────────────────
# _build_kp_catalog_text
# ─────────────────────────────────────────────────────────────────────────────
def test_build_kp_catalog_text_includes_ids_and_names(sample_kps: list[KnowledgePoint]) -> None:
    text = _build_kp_catalog_text(sample_kps)
    assert "kp_sc_verbs" in text
    assert "动词" in text
    assert "kp_sc_prepositions" in text
    assert "介词" in text


def test_build_kp_catalog_text_shows_aliases(sample_kps: list[KnowledgePoint]) -> None:
    text = _build_kp_catalog_text(sample_kps)
    assert "别名: verb" in text


def test_build_kp_catalog_text_omits_alias_section_when_empty(sample_kps: list[KnowledgePoint]) -> None:
    text = _build_kp_catalog_text(sample_kps)
    prep_line = [line for line in text.splitlines() if "kp_sc_prepositions" in line][0]
    assert "别名" not in prep_line


# ─────────────────────────────────────────────────────────────────────────────
# _local_validate
# ─────────────────────────────────────────────────────────────────────────────
def test_local_validate_drops_invalid_kp_ids(sample_kps: list[KnowledgePoint]) -> None:
    resp = GenerateRequest(
        knowledge_points=["kp_sc_verbs", "kp_nonexistent", "kp_bad_id"],
        revision_intensity="light",
        total_questions=10,
    )
    validated, warnings = _local_validate(resp, sample_kps)
    assert validated.knowledge_points == ["kp_sc_verbs"]
    assert len(warnings) == 2
    assert all("invalid KP id" in w for w in warnings)


def test_local_validate_caps_total_questions(sample_kps: list[KnowledgePoint]) -> None:
    resp = GenerateRequest(
        total_questions=100,
        revision_intensity="light",
    )
    validated, warnings = _local_validate(resp, sample_kps)
    assert validated.total_questions == MAX_QUESTIONS
    assert any("capped" in w for w in warnings)


def test_local_validate_scales_oversized_type_distribution(sample_kps: list[KnowledgePoint]) -> None:
    resp = GenerateRequest(
        total_questions=5,
        type_distribution={"single_choice": 10, "word_form": 5},
        revision_intensity="light",
    )
    validated, _ = _local_validate(resp, sample_kps)
    total = sum(validated.type_distribution.values())
    assert total <= validated.total_questions


def test_local_validate_passes_through_valid_response(sample_kps: list[KnowledgePoint]) -> None:
    resp = GenerateRequest(
        knowledge_points=["kp_sc_verbs"],
        question_types=["single_choice"],
        total_questions=10,
        type_distribution={"single_choice": 10},
        revision_intensity="original",
    )
    validated, warnings = _local_validate(resp, sample_kps)
    assert validated.knowledge_points == ["kp_sc_verbs"]
    assert validated.total_questions == 10
    assert validated.revision_intensity == "original"
    assert warnings == []


# ─────────────────────────────────────────────────────────────────────────────
# _build_prompt
# ─────────────────────────────────────────────────────────────────────────────
def test_build_prompt_returns_system_and_user(sample_kps: list[KnowledgePoint]) -> None:
    """Prompt file has no --- separator, so system is empty and user holds all content."""
    system, user = _build_prompt("来十道单选题", "fresh", sample_kps, None, None)
    assert isinstance(system, str)
    assert isinstance(user, str)
    assert len(user) > 0


def test_build_prompt_includes_user_query(sample_kps: list[KnowledgePoint]) -> None:
    _, user = _build_prompt("来十道动词单选题", "fresh", sample_kps, None, None)
    assert "来十道动词单选题" in user


def test_build_prompt_includes_kp_catalog(sample_kps: list[KnowledgePoint]) -> None:
    system, user = _build_prompt("test", "fresh", sample_kps, None, None)
    combined = system + "\n" + user
    assert "kp_sc_verbs" in combined, "KP catalog must appear in the rendered prompt"


def test_build_prompt_includes_wrong_items_for_remediation(sample_kps: list[KnowledgePoint]) -> None:
    wrong_items = [
        WrongItemRef(
            question_type="single_choice",
            knowledge_point_ids=["kp_sc_verbs"],
        )
    ]
    _, user = _build_prompt("多练几道", "remediation", sample_kps, wrong_items, None)
    assert "kp_sc_verbs" in user


def test_build_prompt_includes_mastery_for_review(sample_kps: list[KnowledgePoint]) -> None:
    mastery = MasteryProfile(
        user_id="u_test",
        window_days=30,
        weak_kps=[KPMastery(knowledge_point_id="kp_sc_verbs", attempts=5, mastery=0.3)],
        dominant_types=["single_choice"],
        total_attempts_considered=10,
    )
    _, user = _build_prompt("复习薄弱点", "review", sample_kps, None, mastery)
    assert "kp_sc_verbs" in user


# ─────────────────────────────────────────────────────────────────────────────
# parse() integration tests (require LLM API key + real DB)
# ─────────────────────────────────────────────────────────────────────────────
pytestmark_integration = pytest.mark.integration


@pytestmark_integration
def test_parse_original_intensity_from_natural_language() -> None:
    """'原题' in user query → revision_intensity='original'."""
    req = parse("来十道单选原题")
    assert req.mode == "fresh"
    assert req.total_questions == 10
    assert "single_choice" in req.question_types
    assert req.revision_intensity == "original"
    assert req.free_text == ""


@pytestmark_integration
def test_parse_light_intensity_default() -> None:
    """Generic practice request → revision_intensity is one of light/fresh
    (LLM judgment has inherent variability for ambiguous 'practice' phrasing)."""
    req = parse("来五道单选题练习一下")
    assert req.total_questions == 5
    assert "single_choice" in req.question_types
    assert req.revision_intensity in ("light", "fresh")


@pytestmark_integration
def test_parse_fresh_intensity_from_context() -> None:
    """'重新出' in user query → revision_intensity='fresh'."""
    req = parse("来五道全新的单选题，结合校园场景重新出")
    assert "single_choice" in req.question_types
    assert req.revision_intensity == "fresh"


@pytestmark_integration
def test_parse_review_mode_with_mastery() -> None:
    """Review mode attaches mastery context and user_id."""
    mastery = MasteryProfile(
        user_id="u_test",
        window_days=30,
        weak_kps=[
            KPMastery(knowledge_point_id="kp_sc_verbs", attempts=5, mastery=0.3),
            KPMastery(knowledge_point_id="kp_sc_prepositions", attempts=4, mastery=0.4),
        ],
        dominant_types=["single_choice"],
        total_attempts_considered=20,
    )
    req = parse(
        "帮我复习薄弱点",
        mode="review",
        mastery=mastery,
        user_id="u_test",
        review_window_days=30,
    )
    assert req.mode == "review"
    assert req.user_id == "u_test"
    assert req.review_window_days == 30


@pytestmark_integration
def test_parse_total_questions_capped_at_max() -> None:
    """total_questions > 30 gets capped."""
    req = parse("来一百道单选题")
    assert req.total_questions <= MAX_QUESTIONS


# ─────────────────────────────────────────────────────────────────────────────
# parse() error handling (mocked LLM)
# ─────────────────────────────────────────────────────────────────────────────
def test_parse_raises_on_empty_kp_db(tmp_path: Path) -> None:
    """ParserError when database has no knowledge points."""
    db_path = tmp_path / "empty.db"
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE knowledge_points (
            id TEXT PRIMARY KEY,
            level1 TEXT,
            level2 TEXT,
            aliases_json TEXT
        );
    """)
    conn.commit()
    conn.close()

    with patch("ai_engine.parser.get_config") as mock_cfg:
        mock_cfg.return_value.db_path = str(db_path)
        with pytest.raises(ParserError, match="No knowledge points"):
            parse("来十道单选题")


def test_parse_raises_on_llm_failure(tmp_db: Path, sample_kps: list[KnowledgePoint]) -> None:
    """ParserError when LLM call raises."""
    with patch("ai_engine.parser.get_config") as mock_cfg, \
         patch("ai_engine.parser._load_kp_catalog", return_value=sample_kps), \
         patch("ai_engine.parser.get_llm_client") as mock_client:
        mock_cfg.return_value.db_path = str(tmp_db)
        mock_client.return_value.structured.side_effect = RuntimeError("API timeout")

        with pytest.raises(ParserError, match="LLM call failed"):
            parse("来十道单选题")