"""Unit and integration tests for ai_engine.reviser.

Structure
---------
1. Pure-function unit tests — no I/O, no LLM:
   _infer_title, _copy_question, _validate_revision

2. build_paper unit tests — LLM is mocked via unittest.mock so tests
   run offline and deterministically:
   - original mode: 0 LLM calls, content unchanged, metadata correct
   - light / fresh mode: LLM called once per question
   - invariant violation (question_type changed by LLM) → fallback
   - answer-format violation (bad answer label) → fallback
   - LLM exception → fallback, paper still produced

3. Integration tests — real LLM via DeepSeek API (need DEEPSEEK_API_KEY):
   - light/fresh produce non-trivial modifications
   - invariants always survive a real LLM call
   - answer format always valid after real LLM call
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from unittest.mock import MagicMock, patch

import pytest

from ai_engine.reviser import (
    _copy_question,
    _infer_title,
    _validate_revision,
    build_paper,
)
from shared.schemas import (
    GenerateRequest,
    Option,
    Question,
    RetrievedItem,
    RetrievalResult,
    RevisedQuestion,
)

# ---------------------------------------------------------------------------
# Helpers / shared fixtures
# ---------------------------------------------------------------------------

def _make_sc_question(
    id: str = "q_00001",
    kp_ids: list[str] | None = None,
) -> Question:
    """Minimal valid single_choice Question."""
    return Question(
        id=id,
        book="test_book",
        question_type="single_choice",
        chapter_l1="1 单项选择",
        chapter_l2="1.1 动词",
        number="1",
        stem="Tom ______ to school every day.",
        options=[
            Option(label="A", text="go"),
            Option(label="B", text="goes"),
            Option(label="C", text="going"),
            Option(label="D", text="went"),
        ],
        answer="B",
        knowledge_point_ids=kp_ids or ["kp_sc_verbs"],
        source_md="test.md",
        source_line=1,
        created_at=datetime.now(timezone.utc),
    )


def _make_wf_question(id: str = "q_00002") -> Question:
    """Minimal valid word_form Question."""
    return Question(
        id=id,
        book="test_book",
        question_type="word_form",
        chapter_l1="2 词性转换",
        chapter_l2="2.1 名词",
        number="1",
        stem="He is a great ______ (music).",
        hint="music",
        answer=[{"blank1": ["musician"]}],
        knowledge_point_ids=["kp_wf_noun"],
        source_md="test.md",
        source_line=10,
        created_at=datetime.now(timezone.utc),
    )


def _make_retrieval(questions: list[Question]) -> RetrievalResult:
    return RetrievalResult(
        items=[RetrievedItem(question=q, score=0.9) for q in questions]
    )


def _make_req(
    n: int = 2,
    intensity: Literal["original", "light", "fresh"] = "original",
    question_types: list[str] | None = None,
) -> GenerateRequest:
    return GenerateRequest(
        total_questions=n,
        revision_intensity=intensity,
        question_types=question_types or [],
        free_text="",
    )


# ---------------------------------------------------------------------------
# 1. Pure-function unit tests
# ---------------------------------------------------------------------------

class TestInferTitle:
    def test_original_mode_contains_original(self):
        req = _make_req(n=5, intensity="original", question_types=["single_choice"])
        assert "原题" in _infer_title(req)

    def test_fresh_mode_contains_new(self):
        req = _make_req(n=5, intensity="fresh", question_types=["single_choice"])
        assert "新题" in _infer_title(req)

    def test_light_mode_no_marker(self):
        req = _make_req(n=5, intensity="light", question_types=["single_choice"])
        title = _infer_title(req)
        assert "原题" not in title
        assert "新题" not in title

    def test_no_question_types_falls_back(self):
        req = _make_req(n=3, intensity="light", question_types=[])
        title = _infer_title(req)
        assert isinstance(title, str) and len(title) > 0

    def test_title_always_ends_with_exercise(self):
        for intensity in ("original", "light", "fresh"):
            req = _make_req(n=3, intensity=intensity)
            assert _infer_title(req).endswith("练习")


class TestCopyQuestion:
    def test_fields_match_single_choice(self):
        q = _make_sc_question()
        rq = _copy_question(q)
        assert rq.question_type == q.question_type
        assert rq.stem == q.stem
        assert rq.answer == q.answer
        assert rq.knowledge_point_ids == q.knowledge_point_ids
        assert rq.options is not None
        assert len(rq.options) == 4

    def test_fields_match_word_form(self):
        q = _make_wf_question()
        rq = _copy_question(q)
        assert rq.question_type == q.question_type
        assert rq.hint == q.hint
        assert rq.answer == q.answer

    def test_solution_not_carried_over(self):
        """solution should remain None — Reviser never fills it."""
        q = _make_sc_question()
        rq = _copy_question(q)
        assert rq.solution is None


class TestValidateRevision:
    def _base_revised(self, q: Question) -> RevisedQuestion:
        """Build a valid RevisedQuestion from a Question."""
        return RevisedQuestion(
            question_type=q.question_type,
            knowledge_point_ids=q.knowledge_point_ids,
            stem="Different stem ______.",
            options=[
                Option(label="A", text="opt_a"),
                Option(label="B", text="opt_b"),
                Option(label="C", text="opt_c"),
                Option(label="D", text="opt_d"),
            ],
            answer="A",
        )

    def test_valid_revision_passes(self):
        q = _make_sc_question()
        rq = self._base_revised(q)
        assert _validate_revision(q, rq) is True

    def test_changed_question_type_fails(self):
        q = _make_sc_question()
        rq = self._base_revised(q)
        rq.question_type = "word_form"  # type: ignore[assignment]
        assert _validate_revision(q, rq) is False

    def test_changed_kp_ids_fails(self):
        q = _make_sc_question()
        rq = self._base_revised(q)
        rq.knowledge_point_ids = ["kp_other"]
        assert _validate_revision(q, rq) is False

    def test_bad_answer_label_fails(self):
        q = _make_sc_question()
        rq = self._base_revised(q)
        rq.answer = "E"
        assert _validate_revision(q, rq) is False

    def test_wrong_option_count_fails(self):
        q = _make_sc_question()
        rq = self._base_revised(q)
        rq.options = rq.options[:3]  # only 3 options
        assert _validate_revision(q, rq) is False

    def test_option_labels_incomplete_fails(self):
        q = _make_sc_question()
        rq = self._base_revised(q)
        rq.options = [
            Option(label="A", text="a"),
            Option(label="A", text="a_dup"),  # duplicate A, missing D
            Option(label="B", text="b"),
            Option(label="C", text="c"),
        ]
        assert _validate_revision(q, rq) is False

    def test_empty_fill_in_answer_fails(self):
        q = _make_wf_question()
        # Every structurally-empty fill-in answer must be rejected. These all
        # used to slip through the old `str(answer).strip()` check (a non-empty
        # list stringifies to a truthy repr) but can never be graded correct.
        bad_answers = [
            "",                       # bare empty string
            [],                       # no candidate groups
            [{}],                     # group with no blanks
            [{"blank1": []}],         # blank with no candidates
            [{"blank1": [""]}],       # blank whose only candidate is blank
            [{"blank1": ["  "]}],     # whitespace-only candidate
            [{"blank1": ["ok"], "blank2": []}],  # one good blank, one empty
        ]
        for bad in bad_answers:
            rq = RevisedQuestion(
                question_type="word_form",
                knowledge_point_ids=q.knowledge_point_ids,
                stem=q.stem,
                answer=bad,
            )
            assert _validate_revision(q, rq) is False, f"should reject {bad!r}"

    def test_valid_word_form_passes(self):
        q = _make_wf_question()
        rq = RevisedQuestion(
            question_type="word_form",
            knowledge_point_ids=q.knowledge_point_ids,
            stem="She is a wonderful ______ (music).",
            hint="music",
            answer=[{"blank1": ["musician"]}],
        )
        assert _validate_revision(q, rq) is True


# ---------------------------------------------------------------------------
# 2. build_paper unit tests (LLM mocked)
# ---------------------------------------------------------------------------

def _make_valid_revised_sc(q: Question) -> RevisedQuestion:
    """Build a valid RevisedQuestion that passes _validate_revision."""
    return RevisedQuestion(
        question_type=q.question_type,
        knowledge_point_ids=q.knowledge_point_ids,
        stem="New stem ______.",
        options=[
            Option(label="A", text="alpha"),
            Option(label="B", text="beta"),
            Option(label="C", text="gamma"),
            Option(label="D", text="delta"),
        ],
        answer="C",
    )


class TestBuildPaperOriginalMode:
    def test_no_llm_calls(self):
        q = _make_sc_question()
        req = _make_req(n=1, intensity="original")
        retrieval = _make_retrieval([q])

        with patch("ai_engine.reviser.get_llm_client") as mock_llm:
            paper = build_paper(req, retrieval)

        mock_llm.assert_not_called()
        assert paper.metadata["llm_calls"] == 0

    def test_content_unchanged(self):
        q = _make_sc_question()
        req = _make_req(n=1, intensity="original")
        retrieval = _make_retrieval([q])

        paper = build_paper(req, retrieval)

        item = paper.items[0]
        assert item.question.stem == q.stem
        assert item.question.answer == q.answer
        options_texts = [o.text for o in item.question.options]
        original_texts = [o.text for o in q.options]
        assert options_texts == original_texts

    def test_items_count_and_indices(self):
        qs = [_make_sc_question(f"q_{i:05d}") for i in range(3)]
        req = _make_req(n=3, intensity="original")
        retrieval = _make_retrieval(qs)

        paper = build_paper(req, retrieval)

        assert len(paper.items) == 3
        assert [it.index for it in paper.items] == [1, 2, 3]

    def test_source_question_id_set(self):
        q = _make_sc_question(id="q_00099")
        req = _make_req(n=1, intensity="original")
        retrieval = _make_retrieval([q])

        paper = build_paper(req, retrieval)

        assert paper.items[0].source_question_id == "q_00099"

    def test_revision_mode_recorded(self):
        q = _make_sc_question()
        req = _make_req(n=1, intensity="original")
        retrieval = _make_retrieval([q])

        paper = build_paper(req, retrieval)

        assert paper.items[0].revision_mode == "original"

    def test_paper_has_required_fields(self):
        q = _make_sc_question()
        req = _make_req(n=1, intensity="original")
        retrieval = _make_retrieval([q])

        paper = build_paper(req, retrieval)

        assert paper.paper_id and len(paper.paper_id) > 0
        assert isinstance(paper.generated_at, datetime)
        assert paper.request is req


class TestBuildPaperLightAndFreshMode:
    """LLM is mocked to return a valid RevisedQuestion."""

    @pytest.fixture
    def sc_question(self):
        return _make_sc_question()

    @pytest.fixture
    def mock_client(self, sc_question):
        client = MagicMock()
        client.structured.return_value = _make_valid_revised_sc(sc_question)
        return client

    def test_light_calls_llm_once_per_question(self, sc_question, mock_client):
        qs = [_make_sc_question(f"q_{i:05d}") for i in range(3)]
        req = _make_req(n=3, intensity="light")
        retrieval = _make_retrieval(qs)
        mock_client.structured.return_value = _make_valid_revised_sc(qs[0])

        with patch("ai_engine.reviser.get_llm_client", return_value=mock_client):
            paper = build_paper(req, retrieval)

        assert mock_client.structured.call_count == 3
        assert paper.metadata["llm_calls"] == 3

    def test_fresh_calls_llm_once_per_question(self, sc_question, mock_client):
        qs = [_make_sc_question(f"q_{i:05d}") for i in range(2)]
        req = _make_req(n=2, intensity="fresh")
        retrieval = _make_retrieval(qs)
        mock_client.structured.return_value = _make_valid_revised_sc(qs[0])

        with patch("ai_engine.reviser.get_llm_client", return_value=mock_client):
            paper = build_paper(req, retrieval)

        assert mock_client.structured.call_count == 2
        assert paper.metadata["llm_calls"] == 2

    def test_light_uses_light_prompt(self, sc_question, mock_client):
        req = _make_req(n=1, intensity="light")
        retrieval = _make_retrieval([sc_question])

        with patch("ai_engine.reviser.get_llm_client", return_value=mock_client), \
             patch("ai_engine.reviser.load") as mock_load:
            mock_load.return_value = ("sys", "usr")
            build_paper(req, retrieval)

        # First positional arg to load() must be "reviser_light"
        assert mock_load.call_args[0][0] == "reviser_light"

    def test_fresh_uses_fresh_prompt(self, sc_question, mock_client):
        req = _make_req(n=1, intensity="fresh")
        retrieval = _make_retrieval([sc_question])

        with patch("ai_engine.reviser.get_llm_client", return_value=mock_client), \
             patch("ai_engine.reviser.load") as mock_load:
            mock_load.return_value = ("sys", "usr")
            build_paper(req, retrieval)

        assert mock_load.call_args[0][0] == "reviser_fresh"

    def test_revised_question_replaces_original(self, sc_question, mock_client):
        req = _make_req(n=1, intensity="light")
        retrieval = _make_retrieval([sc_question])
        mock_client.structured.return_value = _make_valid_revised_sc(sc_question)

        with patch("ai_engine.reviser.get_llm_client", return_value=mock_client):
            paper = build_paper(req, retrieval)

        assert paper.items[0].question.stem == "New stem ______."


class TestBuildPaperFallback:
    """Verify the three-layer defence fallback path."""

    def test_invariant_violation_question_type_causes_fallback(self):
        q = _make_sc_question()
        req = _make_req(n=1, intensity="light")
        retrieval = _make_retrieval([q])

        bad_revised = RevisedQuestion(
            question_type="word_form",  # changed → invariant violation
            knowledge_point_ids=q.knowledge_point_ids,
            stem="Different ______.",
            answer="musician",
        )
        client = MagicMock()
        client.structured.return_value = bad_revised

        with patch("ai_engine.reviser.get_llm_client", return_value=client):
            paper = build_paper(req, retrieval)

        # Fallback: content must match the original
        item = paper.items[0]
        assert item.question.stem == q.stem
        assert item.question.answer == q.answer

    def test_invariant_violation_kp_causes_fallback(self):
        q = _make_sc_question()
        req = _make_req(n=1, intensity="light")
        retrieval = _make_retrieval([q])

        bad_revised = RevisedQuestion(
            question_type=q.question_type,
            knowledge_point_ids=["kp_other"],  # changed KP → invariant violation
            stem="Different ______.",
            options=[
                Option(label="A", text="a"),
                Option(label="B", text="b"),
                Option(label="C", text="c"),
                Option(label="D", text="d"),
            ],
            answer="A",
        )
        client = MagicMock()
        client.structured.return_value = bad_revised

        with patch("ai_engine.reviser.get_llm_client", return_value=client):
            paper = build_paper(req, retrieval)

        assert paper.items[0].question.stem == q.stem

    def test_bad_answer_label_causes_fallback(self):
        q = _make_sc_question()
        req = _make_req(n=1, intensity="light")
        retrieval = _make_retrieval([q])

        bad_revised = RevisedQuestion(
            question_type=q.question_type,
            knowledge_point_ids=q.knowledge_point_ids,
            stem="New ______.",
            options=[
                Option(label="A", text="a"),
                Option(label="B", text="b"),
                Option(label="C", text="c"),
                Option(label="D", text="d"),
            ],
            answer="E",  # illegal label → answer-format violation
        )
        client = MagicMock()
        client.structured.return_value = bad_revised

        with patch("ai_engine.reviser.get_llm_client", return_value=client):
            paper = build_paper(req, retrieval)

        assert paper.items[0].question.answer == q.answer

    def test_llm_exception_causes_fallback(self):
        q = _make_sc_question()
        req = _make_req(n=1, intensity="light")
        retrieval = _make_retrieval([q])

        client = MagicMock()
        client.structured.side_effect = RuntimeError("API timeout")

        with patch("ai_engine.reviser.get_llm_client", return_value=client):
            paper = build_paper(req, retrieval)

        # Paper still produced, content equals original
        assert len(paper.items) == 1
        assert paper.items[0].question.stem == q.stem

    def test_fallback_preserves_revision_mode_label(self):
        """Even after fallback, revision_mode in PaperItem stays as requested."""
        q = _make_sc_question()
        req = _make_req(n=1, intensity="light")
        retrieval = _make_retrieval([q])

        client = MagicMock()
        client.structured.side_effect = RuntimeError("oops")

        with patch("ai_engine.reviser.get_llm_client", return_value=client):
            paper = build_paper(req, retrieval)

        assert paper.items[0].revision_mode == "light"

    def test_one_failure_does_not_block_others(self):
        """If one question fails, the rest still get revised successfully."""
        qs = [_make_sc_question(f"q_{i:05d}", kp_ids=["kp_sc_verbs"]) for i in range(3)]
        req = _make_req(n=3, intensity="light")
        retrieval = _make_retrieval(qs)

        valid_revised = _make_valid_revised_sc(qs[0])
        call_count = 0

        def side_effect(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:  # second call fails
                raise RuntimeError("boom")
            return valid_revised

        client = MagicMock()
        client.structured.side_effect = side_effect

        with patch("ai_engine.reviser.get_llm_client", return_value=client):
            paper = build_paper(req, retrieval)

        assert len(paper.items) == 3
        stems = [it.question.stem for it in paper.items]
        # Two revised + one fallback (original stem)
        original_stems = [q.stem for q in qs]
        revised_stem = "New stem ______."
        assert revised_stem in stems
        assert any(s in original_stems for s in stems)


class TestBuildPaperMetadata:
    def test_retrieval_warnings_propagated(self):
        q = _make_sc_question()
        req = _make_req(n=1, intensity="original")
        retrieval = RetrievalResult(
            items=[RetrievedItem(question=q, score=0.0)],
            warnings=["bucket 'single_choice' short of 2"],
            shortfall={"single_choice": 2},
        )

        paper = build_paper(req, retrieval)

        assert "bucket 'single_choice' short of 2" in paper.metadata["retrieval_warnings"]

    def test_shortfall_propagated(self):
        q = _make_sc_question()
        req = _make_req(n=1, intensity="original")
        retrieval = RetrievalResult(
            items=[RetrievedItem(question=q, score=0.0)],
            warnings=["bucket 'single_choice' short of 2"],
            shortfall={"single_choice": 2},
        )

        paper = build_paper(req, retrieval)

        assert paper.metadata["shortfall"] == {"single_choice": 2}

    def test_revision_failures_empty_when_all_succeed(self):
        q = _make_sc_question()
        req = _make_req(n=1, intensity="light")
        retrieval = _make_retrieval([q])
        client = MagicMock()
        client.structured.return_value = _make_valid_revised_sc(q)

        with patch("ai_engine.reviser.get_llm_client", return_value=client):
            paper = build_paper(req, retrieval)

        assert paper.metadata["revision_failures"] == []

    def test_revision_failures_records_fallback_indices(self):
        """When some questions fall back, their 1-based indices are recorded."""
        qs = [_make_sc_question(f"q_{i:05d}", kp_ids=["kp_sc_verbs"]) for i in range(3)]
        req = _make_req(n=3, intensity="light")
        retrieval = _make_retrieval(qs)

        valid_revised = _make_valid_revised_sc(qs[0])
        call_count = 0

        def side_effect(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:  # one call fails → that question falls back
                raise RuntimeError("boom")
            return valid_revised

        client = MagicMock()
        client.structured.side_effect = side_effect

        with patch("ai_engine.reviser.get_llm_client", return_value=client):
            paper = build_paper(req, retrieval)

        # Exactly one question fell back; its index is in the list.
        assert len(paper.metadata["revision_failures"]) == 1
        assert paper.metadata["revision_failures"][0] in {1, 2, 3}

    def test_original_mode_has_no_revision_failures(self):
        q = _make_sc_question()
        req = _make_req(n=1, intensity="original")
        retrieval = _make_retrieval([q])

        paper = build_paper(req, retrieval)

        assert paper.metadata["revision_failures"] == []

    def test_paper_id_is_unique(self):
        q = _make_sc_question()
        req = _make_req(n=1, intensity="original")
        retrieval = _make_retrieval([q])

        p1 = build_paper(req, retrieval)
        p2 = build_paper(req, retrieval)

        assert p1.paper_id != p2.paper_id

    def test_num_questions_capped_by_retrieval(self):
        """If retrieval returns fewer items than total_questions, paper is smaller."""
        q = _make_sc_question()
        req = _make_req(n=5, intensity="original")  # wants 5
        retrieval = _make_retrieval([q])  # only 1 available

        paper = build_paper(req, retrieval)

        assert len(paper.items) == 1


# ---------------------------------------------------------------------------
# 3. Integration tests — real LLM  (need API key, real question bank)
# ---------------------------------------------------------------------------
_resources_ready = (
    Path("data/questions.db").is_file()
    and Path("data/chapters").is_dir()
)

pytestmark_integration = pytest.mark.skipif(
    not _resources_ready,
    reason="requires built data/questions.db and data/chapters/",
)


@pytest.fixture(scope="module")
def real_sc_questions():
    """Load 3 real single-choice questions from the bank."""
    import random
    chapters_dir = Path("data/chapters")
    all_qs: list[dict] = []
    for p in chapters_dir.glob("*.json"):
        with open(p, encoding="utf-8") as f:
            all_qs.extend(json.load(f))
    sc = [q for q in all_qs if q.get("question_type") == "single_choice"]
    random.seed(42)
    random.shuffle(sc)
    results = []
    for q in sc[:3]:
        if "created_at" not in q:
            q["created_at"] = datetime.now(timezone.utc).isoformat()
        results.append(Question(**q))
    return results


@pytest.fixture(scope="module")
def real_retrieval(real_sc_questions):
    return RetrievalResult(
        items=[RetrievedItem(question=q, score=0.9) for q in real_sc_questions]
    )


@pytestmark_integration
def test_integration_original_content_unchanged(real_sc_questions, real_retrieval):
    req = _make_req(n=3, intensity="original")
    paper = build_paper(req, real_retrieval)

    assert len(paper.items) == 3
    for item in paper.items:
        original = next(
            ri.question for ri in real_retrieval.items
            if ri.question.id == item.source_question_id
        )
        assert item.question.stem == original.stem
        assert item.question.answer == original.answer


@pytestmark_integration
def test_integration_invariants_survive_light(real_sc_questions, real_retrieval):
    req = _make_req(n=3, intensity="light")
    paper = build_paper(req, real_retrieval)

    original_map = {ri.question.id: ri.question for ri in real_retrieval.items}
    for item in paper.items:
        orig = original_map[item.source_question_id]
        assert item.question.question_type == orig.question_type
        assert set(item.question.knowledge_point_ids) == set(orig.knowledge_point_ids)


@pytestmark_integration
def test_integration_answer_format_valid_after_light(real_sc_questions, real_retrieval):
    req = _make_req(n=3, intensity="light")
    paper = build_paper(req, real_retrieval)

    for item in paper.items:
        assert item.question.answer in {"A", "B", "C", "D"}
        assert item.question.options and len(item.question.options) == 4
        labels = {opt.label for opt in item.question.options}
        assert labels == {"A", "B", "C", "D"}
        assert item.question.answer in labels


@pytestmark_integration
def test_integration_invariants_survive_fresh(real_sc_questions, real_retrieval):
    req = _make_req(n=3, intensity="fresh")
    paper = build_paper(req, real_retrieval)

    original_map = {ri.question.id: ri.question for ri in real_retrieval.items}
    for item in paper.items:
        orig = original_map[item.source_question_id]
        assert item.question.question_type == orig.question_type
        assert set(item.question.knowledge_point_ids) == set(orig.knowledge_point_ids)
