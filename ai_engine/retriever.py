"""SQL-first retrieval with an optional, lazily loaded vector-ranking path."""
from __future__ import annotations

import random
from pathlib import Path

from ai_engine.errors import RetrieverError
from ai_engine.question_repo import QuestionRepo
from shared.config import get_config
from shared.schemas import GenerateRequest, QuestionType, RetrievedItem, RetrievalResult


def _dot(left: list[float], right: list[float]) -> float:
    return float(sum(a * b for a, b in zip(left, right)))


class Retriever:
    def __init__(self, *, db_path: Path | None = None, chroma_dir: Path | None = None, seed: int | None = None) -> None:
        config = get_config().storage
        self._repo = QuestionRepo(db_path or config.sqlite_path)
        self._chroma_dir = chroma_dir or config.chroma_path
        self._seed = seed
        self._embedder = None
        self._collection = None

    def retrieve(self, req: GenerateRequest) -> RetrievalResult:
        buckets = [([name], amount) for name, amount in req.type_distribution.items() if amount > 0]
        if not buckets:
            buckets = [(list(req.question_types), req.total_questions)]
        result = RetrievalResult()
        seen: set[str] = set()
        for types, needed in buckets:
            ids = [item for item in self._repo.filter_ids(question_types=types or None, knowledge_points=req.knowledge_points or None) if item not in seen]
            ordered, scores = self._rank(ids, req.free_text)
            chosen = ordered[:needed]
            questions = self._repo.get_by_ids(chosen)
            result.items.extend(RetrievedItem(question=questions[qid], score=scores[qid]) for qid in chosen if qid in questions)
            seen.update(chosen)
            if len(chosen) < needed:
                key = types[0] if len(types) == 1 else "all"
                result.shortfall[key] = needed - len(chosen)
                result.warnings.append(f"{key} short of {needed - len(chosen)} question(s)")
        if not result.items:
            raise RetrieverError("no candidates matched the request")
        return result

    def _rank(self, ids: list[str], free_text: str) -> tuple[list[str], dict[str, float]]:
        if not free_text.strip():
            ordered = list(ids)
            random.Random(self._seed).shuffle(ordered)
            return ordered, {qid: 0.0 for qid in ordered}
        try:
            import chromadb
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RetrieverError("vector retrieval dependencies are missing; install requirements.txt") from exc
        if self._embedder is None:
            model_dir = Path("models/Qwen3-Embedding-4B")
            if not model_dir.is_dir():
                raise RetrieverError("embedding model is missing; run models/download_model.py")
            self._embedder = SentenceTransformer(str(model_dir), device="cuda" if _cuda_available() else "cpu")
        if self._collection is None:
            self._collection = chromadb.PersistentClient(path=str(self._chroma_dir)).get_collection("questions")
        vector = self._embedder.encode([free_text], normalize_embeddings=True, convert_to_numpy=True)[0].tolist()
        stored = self._collection.get(ids=ids, include=["embeddings"])
        scores = {qid: _dot(vector, embedding) for qid, embedding in zip(stored["ids"], stored["embeddings"])}
        scores.update({qid: scores.get(qid, 0.0) for qid in ids})
        return sorted(ids, key=lambda qid: scores[qid], reverse=True), scores


def _cuda_available() -> bool:
    try:
        import torch
        return torch.cuda.is_available()
    except ImportError:
        return False


_default: Retriever | None = None


def retrieve(req: GenerateRequest) -> RetrievalResult:
    global _default
    if _default is None:
        _default = Retriever()
    return _default.retrieve(req)
