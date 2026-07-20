"""Unit tests for ai_engine.pipeline (generate_paper orchestration).

All LLM and external resources are mocked so these tests run fully offline.

patch path notes
----------------
pipeline.py lazy-imports submodules INSIDE each function body:
    from ai_engine import parser, retriever, reviser

Patching "ai_engine.parser" / "ai_engine.retriever" / "ai_engine.reviser"
replaces the attribute on the ai_engine package object, which is exactly what
the lazy `from ai_engine import X` expression reads. This works as long as the
submodule has been imported at least once before the patch (so Python has
registered it as a package attribute).  We force that with module-level imports
below.

ai_engine.analyzer doesn't exist yet, so we can't patch it. Instead we patch
ai_engine.pipeline.build_profile directly — that's the internal function
generate_paper calls for the review path.
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

# Force submodule registration so patch("ai_engine.parser", ...) works.
import ai_engine.parser      # noqa: F401  (side-effect: registers pkg attribute)
import ai_engine.retriever   # noqa: F401
import ai_engine.reviser     # noqa: F401

from ai_engine.errors import ParserError, RetrieverError
from ai_engine.pipeline import generate_paper
from shared.schemas import (
    GenerateRequest,
    KPMastery,
    MasteryProfile,
    Option,
    Paper,
    PaperItem,
    Question,
    RetrievedItem,
    RetrievalResult,
    RevisedQuestion,
    WrongItemRef,
)

# ---------------------------------------------------------------------------
# Patch paths
# ---------------------------------------------------------------------------
PARSER_PATH   = "ai_engine.parser"
RETRIEVER_PATH = "ai_engine.retriever"
REVISER_PATH  = "ai_engine.reviser"
# analyzer.py doesn't exist yet; patch the pipeline's own build_profile instead
BUILD_PROFILE_PATH = "ai_engine.pipeline.build_profile"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fake_question(id: str = "q_00001") -> Question:
    return Question(
        id=id, book="b", question_type="single_choice",
        chapter_l1="1", chapter_l2="1.1", number="1",
        stem="______ is correct.",
        options=[
            Option(label="A", text="a"), Option(label="B", text="b"),
            Option(label="C", text="c"), Option(label="D", text="d"),
        ],
        answer="A",
        knowledge_point_ids=["kp_sc_verbs"],
        source_md="t.md", source_line=1,
        created_at=datetime.now(timezone.utc),
    )


def _fake_req(n: int = 5) -> GenerateRequest:
    return GenerateRequest(
        total_questions=n, revision_intensity="light",
        question_types=["single_choice"],
    )


def _fake_retrieval(n: int = 5) -> RetrievalResult:
    return RetrievalResult(
        items=[RetrievedItem(question=_fake_question(f"q_{i:05d}"), score=0.8)
               for i in range(n)]
    )


def _fake_paper(req: GenerateRequest) -> Paper:
    rq = RevisedQuestion(
        question_type="single_choice",
        knowledge_point_ids=["kp_sc_verbs"],
        stem="Revised ______.",
        options=[
            Option(label="A", text="a"), Option(label="B", text="b"),
            Option(label="C", text="c"), Option(label="D", text="d"),
        ],
        answer="A",
    )
    return Paper(
        paper_id="abc123", title="单选练习",
        generated_at=datetime.now(timezone.utc),
        request=req,
        items=[PaperItem(index=1, question=rq,
                         source_question_id="q_00000", revision_mode="light")],
        metadata={},
    )


def _fake_mastery() -> MasteryProfile:
    return MasteryProfile(
        user_id="u_test", window_days=30,
        weak_kps=[KPMastery(knowledge_point_id="kp_sc_verbs",
                            attempts=5, mastery=0.3)],
        dominant_types=["single_choice"],
        total_attempts_considered=20,
    )


# ---------------------------------------------------------------------------
# Convenience: build the three core mocks together
# ---------------------------------------------------------------------------

def _core_mocks(req=None, retrieval=None):
    req = req or _fake_req()
    retrieval = retrieval or _fake_retrieval()
    mock_parser = MagicMock()
    mock_parser.parse.return_value = req
    mock_retriever = MagicMock()
    mock_retriever.retrieve.return_value = retrieval
    mock_reviser = MagicMock()
    mock_reviser.build_paper.return_value = _fake_paper(req)
    return req, retrieval, mock_parser, mock_retriever, mock_reviser


# ---------------------------------------------------------------------------
# Tests: fresh mode
# ---------------------------------------------------------------------------

class TestGeneratePaperFreshMode:

    def test_returns_paper_from_reviser(self):
        req, retrieval, mp, mr, mv = _core_mocks()
        with patch(PARSER_PATH, mp), patch(RETRIEVER_PATH, mr), patch(REVISER_PATH, mv):
            paper = generate_paper("来五道单选题")
        assert paper.paper_id == "abc123"

    def test_parser_called_once_with_query(self):
        req, retrieval, mp, mr, mv = _core_mocks()
        with patch(PARSER_PATH, mp), patch(RETRIEVER_PATH, mr), patch(REVISER_PATH, mv):
            generate_paper("来五道单选题")
        mp.parse.assert_called_once()
        assert mp.parse.call_args[0][0] == "来五道单选题"

    def test_retriever_called_with_parser_output(self):
        req, retrieval, mp, mr, mv = _core_mocks()
        with patch(PARSER_PATH, mp), patch(RETRIEVER_PATH, mr), patch(REVISER_PATH, mv):
            generate_paper("来五道题")
        mr.retrieve.assert_called_once_with(req)

    def test_reviser_called_with_req_and_retrieval(self):
        req, retrieval, mp, mr, mv = _core_mocks()
        with patch(PARSER_PATH, mp), patch(RETRIEVER_PATH, mr), patch(REVISER_PATH, mv):
            generate_paper("来五道题")
        mv.build_paper.assert_called_once_with(req, retrieval)

    def test_build_profile_not_called_in_fresh_mode(self):
        req, retrieval, mp, mr, mv = _core_mocks()
        mock_bp = MagicMock()
        with patch(PARSER_PATH, mp), patch(RETRIEVER_PATH, mr), \
             patch(REVISER_PATH, mv), patch(BUILD_PROFILE_PATH, mock_bp):
            generate_paper("来五道题")
        mock_bp.assert_not_called()

    def test_fresh_mode_passes_mode_to_parser(self):
        req, retrieval, mp, mr, mv = _core_mocks()
        with patch(PARSER_PATH, mp), patch(RETRIEVER_PATH, mr), patch(REVISER_PATH, mv):
            generate_paper("来五道单选题", mode="fresh")
        _, call_kw = mp.parse.call_args
        assert call_kw.get("mode") == "fresh"


# ---------------------------------------------------------------------------
# Tests: remediation mode
# ---------------------------------------------------------------------------

class TestGeneratePaperRemediationMode:

    def test_wrong_items_forwarded_to_parser(self):
        req, retrieval, mp, mr, mv = _core_mocks()
        wrong_items = [WrongItemRef(question_type="single_choice",
                                   knowledge_point_ids=["kp_sc_verbs"])]
        with patch(PARSER_PATH, mp), patch(RETRIEVER_PATH, mr), patch(REVISER_PATH, mv):
            generate_paper("再练练这些错题", mode="remediation",
                           wrong_items=wrong_items)
        _, call_kw = mp.parse.call_args
        assert call_kw.get("wrong_items") == wrong_items
        assert call_kw.get("mode") == "remediation"

    def test_build_profile_not_called_in_remediation(self):
        req, retrieval, mp, mr, mv = _core_mocks()
        mock_bp = MagicMock()
        with patch(PARSER_PATH, mp), patch(RETRIEVER_PATH, mr), \
             patch(REVISER_PATH, mv), patch(BUILD_PROFILE_PATH, mock_bp):
            generate_paper("来几道", mode="remediation",
                           wrong_items=[WrongItemRef(
                               question_type="single_choice",
                               knowledge_point_ids=["kp_sc_verbs"]
                           )])
        mock_bp.assert_not_called()


# ---------------------------------------------------------------------------
# Tests: review mode
# ---------------------------------------------------------------------------

class TestGeneratePaperReviewMode:

    def test_raises_parser_error_without_user_id(self):
        with pytest.raises(ParserError, match="user_id"):
            generate_paper("复习薄弱点", mode="review")

    def test_build_profile_called_with_user_id_and_window(self):
        req, retrieval, mp, mr, mv = _core_mocks()
        mastery = _fake_mastery()
        mock_bp = MagicMock(return_value=mastery)
        with patch(PARSER_PATH, mp), patch(RETRIEVER_PATH, mr), \
             patch(REVISER_PATH, mv), patch(BUILD_PROFILE_PATH, mock_bp):
            generate_paper("复习薄弱点", mode="review",
                           user_id="u_test", review_window_days=30)
        mock_bp.assert_called_once_with("u_test", 30)

    def test_mastery_profile_forwarded_to_parser(self):
        req, retrieval, mp, mr, mv = _core_mocks()
        mastery = _fake_mastery()
        mock_bp = MagicMock(return_value=mastery)
        with patch(PARSER_PATH, mp), patch(RETRIEVER_PATH, mr), \
             patch(REVISER_PATH, mv), patch(BUILD_PROFILE_PATH, mock_bp):
            generate_paper("复习薄弱点", mode="review",
                           user_id="u_test", review_window_days=30)
        _, call_kw = mp.parse.call_args
        assert call_kw.get("mastery") is mastery
        assert call_kw.get("mode") == "review"

    def test_review_window_days_14_forwarded_to_build_profile(self):
        req, retrieval, mp, mr, mv = _core_mocks()
        mastery = _fake_mastery()
        mock_bp = MagicMock(return_value=mastery)
        with patch(PARSER_PATH, mp), patch(RETRIEVER_PATH, mr), \
             patch(REVISER_PATH, mv), patch(BUILD_PROFILE_PATH, mock_bp):
            generate_paper("复习薄弱点", mode="review",
                           user_id="u_test", review_window_days=14)
        mock_bp.assert_called_once_with("u_test", 14)

    def test_user_id_and_window_set_on_req_by_pipeline(self):
        req, retrieval, mp, mr, mv = _core_mocks()
        mastery = _fake_mastery()
        mock_bp = MagicMock(return_value=mastery)
        with patch(PARSER_PATH, mp), patch(RETRIEVER_PATH, mr), \
             patch(REVISER_PATH, mv), patch(BUILD_PROFILE_PATH, mock_bp):
            paper = generate_paper("复习薄弱点", mode="review",
                                   user_id="u_test", review_window_days=30)
        # pipeline sets these directly on req after parse() returns
        assert paper.request.user_id == "u_test"
        assert paper.request.review_window_days == 30



class TestGeneratePaperErrorPropagation:

    def test_parser_error_propagates(self):
        mp = MagicMock()
        mp.parse.side_effect = ParserError("parse failed")
        with patch(PARSER_PATH, mp), patch(RETRIEVER_PATH, MagicMock()), \
             patch(REVISER_PATH, MagicMock()):
            with pytest.raises(ParserError, match="parse failed"):
                generate_paper("来几道题")

    def test_retriever_error_propagates(self):
        req, _, mp, mr, mv = _core_mocks()
        mr.retrieve.side_effect = RetrieverError("no candidates")
        with patch(PARSER_PATH, mp), patch(RETRIEVER_PATH, mr), patch(REVISER_PATH, mv):
            with pytest.raises(RetrieverError, match="no candidates"):
                generate_paper("来几道题")

    def test_reviser_never_reached_when_retriever_fails(self):
        req, _, mp, mr, mv = _core_mocks()
        mr.retrieve.side_effect = RetrieverError("empty")
        with patch(PARSER_PATH, mp), patch(RETRIEVER_PATH, mr), patch(REVISER_PATH, mv):
            with pytest.raises(RetrieverError):
                generate_paper("来几道题")
        mv.build_paper.assert_not_called()
