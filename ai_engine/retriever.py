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
import re
from pathlib import Path

from ai_engine.errors import RetrieverError
from ai_engine.question_repo import DEFAULT_DB_PATH, QuestionRepo
from shared.schemas import (
    GenerateRequest,
    Question,
    QuestionType,
    RetrievalResult,
    RetrievedItem,
)

log = logging.getLogger(__name__)

DEFAULT_CHROMA_DIR = Path("data/chroma")
COLLECTION_NAME = "questions"

# Over-fetch factor for the vector path: pull this many × the bucket target
# from Chroma before intersecting with the SQL hard-filter set, so enough
# survive the intersection. (Spec B §4.2 step 3.)
OVER_FETCH = 3

# free_text is treated as "semantic" only if it has enough Chinese/English
# content to be worth embedding. A bare "" or "来10道题" carries no topic.
_MEANINGFUL_CHARS = re.compile(r"[一-鿿A-Za-z]")
_MIN_SEMANTIC_CHARS = 4


def _has_semantic_intent(free_text: str) -> bool:
    """Decide whether free_text warrants a vector search (D2 switch)."""
    chars = _MEANINGFUL_CHARS.findall(free_text or "")
    return len(chars) >= _MIN_SEMANTIC_CHARS


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
        # 1. SQL hard-filter → candidate id set for this bucket
        hard_ids = self._repo.filter_ids(
            question_types=bucket_qtypes or None,
            knowledge_points=req.knowledge_points or None,
        )
        hard_ids = [i for i in hard_ids if i not in exclude]
        if not hard_ids:
            return []

        if use_vector:
            ordered_ids, scores = self._vector_order(req, bucket_qtypes, hard_ids, target)
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
        bucket_qtypes: list[QuestionType],
        hard_ids: list[str],
        target: int,
    ) -> tuple[list[str], dict[str, float]]:
        """Embed free_text, pull Top-M from Chroma, intersect with hard_ids,
        order by similarity. Returns (ordered_ids, id→score).

        Chroma metadata filter narrows by question_type (cheap); the KP filter
        stays in SQL (hard_ids) because kp_ids is a comma-joined string in
        metadata and exact matching there is unreliable (Spec A §3.8)."""
        hard_set = set(hard_ids)
        embedder = self._get_embedder()
        collection = self._get_collection()

        query_vec = embedder.embed([req.free_text])[0]

        where = None
        if bucket_qtypes:
            where = (
                {"question_type": bucket_qtypes[0]}
                if len(bucket_qtypes) == 1
                else {"question_type": {"$in": list(bucket_qtypes)}}
            )

        # Over-fetch: intersection with hard_set drops some hits, so pull extra.
        m = min(len(hard_ids), max(target * OVER_FETCH, target))
        res = collection.query(
            query_embeddings=[query_vec],
            n_results=m,
            where=where,
            include=["distances"],
        )
        hit_ids = res["ids"][0]
        distances = res["distances"][0]

        ordered: list[str] = []
        scores: dict[str, float] = {}
        for qid, dist in zip(hit_ids, distances):
            if qid in hard_set:
                ordered.append(qid)
                scores[qid] = 1.0 - dist       # cosine distance → similarity
        # If the vector hits under-cover the bucket (e.g. Chroma returned fewer
        # than needed after intersection), top up with the remaining hard_ids
        # in deterministic order so we still hit the target when possible.
        if len(ordered) < target:
            remaining = [i for i in hard_ids if i not in scores]
            ordered.extend(remaining)
            for i in remaining:
                scores.setdefault(i, 0.0)
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
