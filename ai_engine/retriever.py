"""Retriever (Spec B §4): GenerateRequest → candidate questions.

Hybrid retrieval — attribute hard-filter (SQL) combined with optional
semantic vector search (ChromaDB + Qwen), plus per-bucket quota allocation.

Bucketing (D1)
    * `req.type_distribution` non-empty → one bucket per question type, each
      taking its requested count.
    * otherwise → a single bucket taking `req.total_questions`, constrained by
      `req.question_types` / `req.knowledge_points` if given.

Per-bucket selection (D2 — the "hybrid" bit)
    * `req.free_text` carries real semantic intent ("关于环保的时态题") →
      VECTOR path: embed free_text, pull Top-M from Chroma, intersect with the
      bucket's SQL hard-filter set, order by cosine similarity.
    * free_text empty / trivial → SQL path: hard-filter, then random sample
      (seeded, D3) so papers vary run-to-run yet stay reproducible in tests.

Shortfall (兜底)
    A bucket that can't reach its target records the gap in
    `RetrievalResult.shortfall`. Retriever never fabricates questions — the
    Reviser decides whether to fresh-generate the gap (and whether it's allowed
    to, per revision_intensity). See RetrievalResult docstring.

Cost note: the Qwen embedder is loaded lazily — a pure-quota request
("5 单选 5 改写", no free_text) never touches the model.
"""
from __future__ import annotations

import logging
import random
from pathlib import Path

from ai_engine.errors import RetrieverError
from ai_engine.question_repo import DEFAULT_DB_PATH, QuestionRepo
from shared.schemas import (
    GenerateRequest,
    PASSAGE_QUESTION_TYPES,
    Question,
    QuestionType,
    RetrievalResult,
    RetrievedItem,
)

log = logging.getLogger(__name__)

DEFAULT_CHROMA_DIR = Path("data/chroma")
COLLECTION_NAME = "questions"

# Question types that share a passage and must be retrieved as a whole group
# (never enter the vector store — SQL-only, grouped by passage_id).
# Writing questions also don't enter the vector store (no correct answer to embed).
# Shared with reviser (passthrough) via shared.schemas.PASSAGE_QUESTION_TYPES.
PASSAGE_TYPES = PASSAGE_QUESTION_TYPES


def _dot(a, b) -> float:
    """Dot product of two equal-length vectors. Both the query and stored
    vectors are L2-normalised (build_vec uses normalize_embeddings=True), so
    the dot product equals cosine similarity."""
    return float(sum(x * y for x, y in zip(a, b)))


def _has_semantic_intent(free_text: str) -> bool:
    """Whether free_text warrants a vector search (D2 switch).

    The Parser fills `free_text` ONLY with a leftover semantic topic that the
    structured fields can't express (see GenerateRequest.free_text docstring);
    a pure quota/KP request leaves it "". So the switch is simply "non-empty":
    empty → SQL random path, non-empty → vector path.
    """
    return bool(free_text and free_text.strip())


def _auto_device() -> str:
    """Pick 'cuda' when available, else 'cpu'. Lets the same code run on the
    GPU build machine and on CPU-only dev/test boxes without a manual flag."""
    try:
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"


class Retriever:
    """Hybrid retriever over the question bank + vector store.

    Embedder is created lazily and cached; only vector-path requests pay the
    model-load cost.
    """

    def __init__(
        self,
        *,
        db_path: Path = DEFAULT_DB_PATH,
        chroma_dir: Path = DEFAULT_CHROMA_DIR,
        seed: int | None = None,
        embedder_cfg=None,
    ) -> None:
        self._repo = QuestionRepo(db_path)
        self._chroma_dir = chroma_dir
        self._seed = seed
        self._embedder_cfg = embedder_cfg
        self._embedder = None          # lazy
        self._collection = None        # lazy

    # ─── lazy resources ──────────────────────────────────────────────
    def _get_embedder(self):
        if self._embedder is None:
            from ingestion.chromadb.embedder import EmbedderConfig, QwenEmbedder
            cfg = self._embedder_cfg or EmbedderConfig(device=_auto_device())
            self._embedder = QwenEmbedder(cfg)
        return self._embedder

    def _get_collection(self):
        if self._collection is None:
            import chromadb
            client = chromadb.PersistentClient(path=str(self._chroma_dir))
            self._collection = client.get_collection(COLLECTION_NAME)
        return self._collection

    # ─── public entry ────────────────────────────────────────────────
    def retrieve(self, req: GenerateRequest) -> RetrievalResult:
        """GenerateRequest → RetrievalResult (candidate pool + shortfall)."""
        buckets = self._plan_buckets(req)

        items: list[RetrievedItem] = []
        warnings: list[str] = []
        shortfall: dict[str, int] = {}
        seen_ids: set[str] = set()
        use_vector = _has_semantic_intent(req.free_text)

        for bucket_qtypes, target in buckets:
            got = self._fill_bucket(
                req=req,
                bucket_qtypes=bucket_qtypes,
                target=target,
                use_vector=use_vector,
                exclude=seen_ids,
            )
            for it in got:
                seen_ids.add(it.question.id)
            items.extend(got)

            if len(got) < target:
                gap = target - len(got)
                key = bucket_qtypes[0] if len(bucket_qtypes) == 1 else "all"
                shortfall[key] = shortfall.get(key, 0) + gap
                warnings.append(
                    f"bucket {key!r} short of {gap} question(s) "
                    f"(needed {target}, found {len(got)})"
                )

        if not items:
            raise RetrieverError(
                "no candidates matched the request "
                f"(types={req.question_types}, kps={req.knowledge_points})"
            )

        return RetrievalResult(items=items, warnings=warnings, shortfall=shortfall)

    # ─── bucket planning (D1) ────────────────────────────────────────
    def _plan_buckets(self, req: GenerateRequest) -> list[tuple[list[QuestionType], int]]:
        """Return [(question_types_for_bucket, target_count), ...].

        With type_distribution → one bucket per type. Without → a single bucket
        covering req.question_types (or all types) for total_questions.
        """
        if req.type_distribution:
            buckets: list[tuple[list[QuestionType], int]] = []
            for qtype, n in req.type_distribution.items():
                if n > 0:
                    buckets.append(([qtype], n))  # type: ignore[list-item]
            return buckets
        # single bucket
        return [(list(req.question_types), req.total_questions)]

    # ─── bucket fill ─────────────────────────────────────────────────
    def _fill_bucket(
        self,
        *,
        req: GenerateRequest,
        bucket_qtypes: list[QuestionType],
        target: int,
        use_vector: bool,
        exclude: set[str],
    ) -> list[RetrievedItem]:
        """Retrieve up to `target` items for one bucket."""
        # Passage-based types (listening_true_false) are retrieved as whole
        # passage groups via SQL only — never the vector path.
        if set(bucket_qtypes) & PASSAGE_TYPES:
            return self._fill_bucket_passage(req, bucket_qtypes, target, exclude)

        # 1. SQL hard-filter → candidate id set for this bucket
        hard_ids = self._repo.filter_ids(
            question_types=bucket_qtypes or None,
            knowledge_points=req.knowledge_points or None,
        )
        hard_ids = [i for i in hard_ids if i not in exclude]
        if not hard_ids:
            return []

        if use_vector:
            ordered_ids, scores = self._vector_order(req, hard_ids)
        else:
            ordered_ids = self._random_order(hard_ids)
            scores = {i: 0.0 for i in ordered_ids}

        chosen = ordered_ids[:target]
        questions = self._repo.get_by_ids(chosen)
        # preserve chosen order (get_by_ids returns a dict)
        out: list[RetrievedItem] = []
        for qid in chosen:
            q = questions.get(qid)
            if q is not None:
                out.append(RetrievedItem(question=q, score=scores.get(qid, 0.0)))
        return out

    # ─── passage-group path (listening_true_false) ──────────────────
    def _fill_bucket_passage(
        self,
        req: GenerateRequest,
        bucket_qtypes: list[QuestionType],
        target: int,
        exclude: set[str],
    ) -> list[RetrievedItem]:
        """Retrieve whole passage groups for passage-based types.

    Picks random passage_ids, takes ALL questions under each, until the
    cumulative count reaches `target`. Once at least one passage has been
    selected, a subsequent passage that would push the count past `target`
    is skipped — passage integrity outweighs exact count, and crossing
    passages just to fill the quota would turn "1 passage" into "2 passages".
    """
        hard_ids = self._repo.filter_ids(
            question_types=bucket_qtypes or None,
            knowledge_points=req.knowledge_points or None,
        )
        hard_ids = [i for i in hard_ids if i not in exclude]
        if not hard_ids:
            return []

        questions = self._repo.get_by_ids(hard_ids)
        # Group by passage_id (solo questions without passage_id fall back to
        # their own id so each is its own "group" of 1).
        groups: dict[str, list[str]] = {}
        for qid, q in questions.items():
            pid = q.passage_id or f"solo-{qid}"
            groups.setdefault(pid, []).append(qid)

        rng = random.Random(self._seed)
        passage_ids = list(groups.keys())
        rng.shuffle(passage_ids)

        chosen_ids: list[str] = []
        for pid in passage_ids:
            if len(chosen_ids) >= target:
                break
            # 已选至少一篇后，若加入下一篇会超过目标题数，则停止——
            # passage 完整性优先，宁可少给几题也不跨篇凑数（避免"1 篇变 2 篇"）。
            if chosen_ids and len(chosen_ids) + len(groups[pid]) > target:
                break
            chosen_ids.extend(groups[pid])

        out: list[RetrievedItem] = []
        for qid in chosen_ids:
            q = questions.get(qid)
            if q is not None:
                out.append(RetrievedItem(question=q, score=0.0))
        return out

    # ─── SQL random path (D3) ────────────────────────────────────────
    def _random_order(self, ids: list[str]) -> list[str]:
        rng = random.Random(self._seed)   # seeded → reproducible in tests
        shuffled = list(ids)
        rng.shuffle(shuffled)
        return shuffled

    # ─── vector path (D2/D3) ─────────────────────────────────────────
    def _vector_order(
        self,
        req: GenerateRequest,
        hard_ids: list[str],
    ) -> tuple[list[str], dict[str, float]]:
        """Rank the SQL-filtered candidates (`hard_ids`) by semantic similarity
        to `free_text`. Returns (ordered_ids, id→score).

        Order is SQL-first, vector-second: `hard_ids` is already the exact
        candidate set (question_type + KP filtered in SQL). We fetch *those*
        questions' stored vectors from Chroma by id and score them locally
        against the query vector, then sort. This guarantees the ranking is
        over the intended KP set — never "the globally-nearest 15, of which
        only 2 happen to be in-set" (the old query()+intersect bug).

        Chroma's query() can't be limited to an id set, so we use get(ids=...)
        + local cosine instead. Vectors were L2-normalised at build time, so
        cosine == dot product.
        """
        embedder = self._get_embedder()
        collection = self._get_collection()

        query_vec = embedder.embed([req.free_text])[0]

        stored = collection.get(ids=hard_ids, include=["embeddings"])
        got_ids = stored["ids"]
        embeddings = stored["embeddings"]

        scores: dict[str, float] = {}
        for qid, vec in zip(got_ids, embeddings):
            scores[qid] = _dot(query_vec, vec)   # both normalised → cosine

        # Any hard_id missing from Chroma (shouldn't happen if the vector store
        # is in sync with SQLite) falls to the end with score 0.
        for qid in hard_ids:
            scores.setdefault(qid, 0.0)

        ordered = sorted(hard_ids, key=lambda i: scores[i], reverse=True)
        return ordered, scores


# ─── module-level convenience (matches Spec B §2.2 pipeline call) ────────────
_default_retriever: Retriever | None = None


def retrieve(req: GenerateRequest) -> RetrievalResult:
    """Module-level entry using a lazily-created default Retriever.

    pipeline.py calls `retriever.retrieve(req)`; tests instantiate `Retriever`
    directly with a seed / custom paths.
    """
    global _default_retriever
    if _default_retriever is None:
        _default_retriever = Retriever()
    return _default_retriever.retrieve(req)
