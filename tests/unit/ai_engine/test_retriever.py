"""Unit tests for ai_engine.retriever against the real question bank.

Uses real resources (no mocks): data/questions.db (1066 questions),
data/chroma/ (1066 vectors), models/Qwen3-Embedding-4B. Tests therefore
exercise the true hybrid-retrieval behaviour end to end, including the
semantic (RAG) path.

Five representative input samples (see SAMPLES) cover every retrieval path:
    1. type_distribution buckets         (SQL random, quota split)
    2. single bucket + KP filter          (SQL random, KP join)
    3. free_text semantic query           (vector path — RAG relevance)
    4. requested count > bank supply       (shortfall reporting)
    5. no filter at all                    (whole-bank random)

The vector-path test loads the Qwen model, so the module is a bit slow; that
is intentional — we want a faithful check, not a stub.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest

from ai_engine.errors import RetrieverError
from ai_engine.retriever import Retriever, _has_semantic_intent
from shared.schemas import GenerateRequest, RetrievalResult

DB_PATH = Path("data/questions.db")
CHROMA_DIR = Path("data/chroma")

# Skip the whole module if the real resources aren't present (e.g. a fresh
# checkout without the built DB/vectors). Keeps CI honest rather than failing
# with confusing FileNotFoundErrors.
_resources_ready = DB_PATH.is_file() and CHROMA_DIR.is_dir()
pytestmark = pytest.mark.skipif(
    not _resources_ready,
    reason="requires built data/questions.db + data/chroma/",
)


# ─────────────────────────────────────────────────────────────────────────────
# Five representative request samples
# ─────────────────────────────────────────────────────────────────────────────
SAMPLES: dict[str, GenerateRequest] = {
    # 1. "5 道单选 + 5 道改写" — type_distribution buckets, no semantics
    "type_distribution": GenerateRequest(
        total_questions=10,
        type_distribution={"single_choice": 5, "sentence_rewriting": 5},
    ),
    # 2. "8 道时态单选" — single bucket, KP + type filter
    "kp_filter": GenerateRequest(
        total_questions=8,
        knowledge_points=["kp_sc_verbs"],
        question_types=["single_choice"],
    ),
    # 3. "来几道关于环保的单选" — Parser extracts topic → free_text="关于环保
    #    环境保护 污染"; triggers the vector path
    "semantic": GenerateRequest(
        total_questions=5,
        question_types=["single_choice"],
        free_text="关于环保 环境保护 污染",
    ),
    # 4. "50 道 kp_sc_misc（库里仅 2 道）" — shortfall
    "shortfall": GenerateRequest(
        total_questions=50,
        knowledge_points=["kp_sc_misc"],
        question_types=["single_choice"],
    ),
    # 5. "随便 5 道" — no filter, whole-bank random
    "unrestricted": GenerateRequest(total_questions=5),
}


@pytest.fixture(scope="module")
def retriever() -> Retriever:
    """Seeded retriever so SQL-random paths are reproducible across the run."""
    return Retriever(db_path=DB_PATH, chroma_dir=CHROMA_DIR, seed=42)


# ─────────────────────────────────────────────────────────────────────────────
# Sample 1 — type_distribution buckets
# ─────────────────────────────────────────────────────────────────────────────
def test_type_distribution_exact_quota(retriever: Retriever) -> None:
    res = retriever.retrieve(SAMPLES["type_distribution"])
    assert isinstance(res, RetrievalResult)
    assert len(res.items) == 10
    counts = Counter(it.question.question_type for it in res.items)
    assert counts["single_choice"] == 5
    assert counts["sentence_rewriting"] == 5
    assert res.shortfall == {}


def test_type_distribution_no_duplicate_ids(retriever: Retriever) -> None:
    res = retriever.retrieve(SAMPLES["type_distribution"])
    ids = [it.question.id for it in res.items]
    assert len(ids) == len(set(ids))          # no question picked twice


# ─────────────────────────────────────────────────────────────────────────────
# Sample 2 — single bucket + KP filter
# ─────────────────────────────────────────────────────────────────────────────
def test_kp_filter_all_match(retriever: Retriever) -> None:
    res = retriever.retrieve(SAMPLES["kp_filter"])
    assert len(res.items) == 8
    for it in res.items:
        assert it.question.question_type == "single_choice"
        assert "kp_sc_verbs" in it.question.knowledge_point_ids
    assert res.shortfall == {}


# ─────────────────────────────────────────────────────────────────────────────
# Sample 3 — semantic vector path (RAG)
# ─────────────────────────────────────────────────────────────────────────────
def test_semantic_query_returns_relevant(retriever: Retriever) -> None:
    """The environment-themed query should surface questions whose stems are
    about environment/pollution — content the SQL filters cannot express."""
    res = retriever.retrieve(SAMPLES["semantic"])
    assert len(res.items) == 5
    assert all(it.question.question_type == "single_choice" for it in res.items)

    # Vector path assigns real similarity scores (SQL random path leaves 0.0).
    assert any(it.score > 0 for it in res.items)
    # Results ordered by descending similarity.
    scores = [it.score for it in res.items if it.score > 0]
    assert scores == sorted(scores, reverse=True)

    # Relevance check: at least some stems mention environment vocabulary.
    # Kept loose — embeddings aren't deterministic in ranking, but the theme
    # should clearly dominate versus a random draw.
    vocab = ("environment", "pollution", "carbon", "climate",
             "rubbish", "recycl", "friendly", "waste", "energy")
    hits = sum(
        1 for it in res.items
        if it.question.stem and any(w in it.question.stem.lower() for w in vocab)
    )
    assert hits >= 2, f"expected environment-themed stems, got {hits}/5"


# ─────────────────────────────────────────────────────────────────────────────
# Sample 4 — shortfall
# ─────────────────────────────────────────────────────────────────────────────
def test_shortfall_reported_when_bank_too_small(retriever: Retriever) -> None:
    res = retriever.retrieve(SAMPLES["shortfall"])
    # kp_sc_misc has only 2 questions in the bank.
    assert len(res.items) == 2
    assert res.shortfall == {"single_choice": 48}
    assert res.warnings                       # a human-readable warning too
    # Retriever never fabricates — it reports the gap, Reviser fills it.
    for it in res.items:
        assert "kp_sc_misc" in it.question.knowledge_point_ids


# ─────────────────────────────────────────────────────────────────────────────
# Sample 5 — unrestricted
# ─────────────────────────────────────────────────────────────────────────────
def test_unrestricted_draws_from_whole_bank(retriever: Retriever) -> None:
    res = retriever.retrieve(SAMPLES["unrestricted"])
    assert len(res.items) == 5
    assert res.shortfall == {}


# ─────────────────────────────────────────────────────────────────────────────
# Cross-cutting behaviour
# ─────────────────────────────────────────────────────────────────────────────
def test_seed_makes_sql_path_reproducible() -> None:
    """Two retrievers with the same seed return the same ids on the SQL path."""
    req = SAMPLES["unrestricted"]
    r1 = Retriever(db_path=DB_PATH, chroma_dir=CHROMA_DIR, seed=7)
    r2 = Retriever(db_path=DB_PATH, chroma_dir=CHROMA_DIR, seed=7)
    ids1 = [it.question.id for it in r1.retrieve(req).items]
    ids2 = [it.question.id for it in r2.retrieve(req).items]
    assert ids1 == ids2


def test_returned_questions_are_complete(retriever: Retriever) -> None:
    """Retrieved items carry fully-populated Question objects (for the Reviser)."""
    res = retriever.retrieve(SAMPLES["kp_filter"])
    q = res.items[0].question
    assert q.id and q.book and q.question_type
    assert q.answer is not None
    # single_choice must have options
    assert q.options and len(q.options) >= 2


def test_empty_candidate_set_raises() -> None:
    """A filter matching nothing raises RetrieverError rather than returning []."""
    r = Retriever(db_path=DB_PATH, chroma_dir=CHROMA_DIR, seed=1)
    req = GenerateRequest(
        total_questions=5,
        knowledge_points=["kp_does_not_exist"],
    )
    with pytest.raises(RetrieverError):
        r.retrieve(req)


# ─────────────────────────────────────────────────────────────────────────────
# _has_semantic_intent unit (pure, no resources)
# ─────────────────────────────────────────────────────────────────────────────
# Parser fills free_text ONLY with a leftover semantic topic; a pure quota/KP
# request leaves it "". So the switch is simply "non-empty (after strip)".
@pytest.mark.parametrize("text,expected", [
    ("", False),
    ("   ", False),
    (None, False),
    ("关于环保", True),
    ("结合校园生活", True),
    ("environment pollution", True),
])
def test_has_semantic_intent(text: str | None, expected: bool) -> None:
    assert _has_semantic_intent(text) is expected
