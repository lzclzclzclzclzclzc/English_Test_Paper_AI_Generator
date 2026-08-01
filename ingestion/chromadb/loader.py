"""Stage 5: load the question bank into ChromaDB.

Reads:
    data/questions.db                — SQLite question bank (§3.7)
    (Qwen3-Embedding-4B, pre-downloaded, loaded by embedder.py)

Writes:
    data/chroma/                     — ChromaDB persistent client, collection `questions`

Per Spec §3.8:
    ids       ← Question.id                        ("q_00042")
    documents ← embedding_text (built from §2.5)   — stored for debugging &
                                                     model-swap reruns
    embeddings ← Qwen embedding output (2560-dim, L2-normalised)
    metadatas ← {
                    question_type, book, chapter_l1, chapter_l2,
                    kp_ids  (comma-separated, since Chroma metadata forbids lists)
                }

Idempotent by `Question.id`:
    On rerun, ids already present in the collection are skipped — no
    re-embedding of unchanged rows. To rebuild vectors for an edited row,
    delete it from the collection first (or drop `data/chroma/`).

Retrieval hint (for future Retriever, Spec B):
    * cosine distance against the same-space query vector
    * hard-filter with `where={"question_type": "single_choice"}` etc.
    * for kp_ids, use metadata `$contains` — the value is a `"kp_a,kp_b"` string
"""
from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ingestion.chromadb.embedder import EmbedderConfig, QwenEmbedder
from ingestion.chromadb.embedding_text import build_embedding_text

log = logging.getLogger(__name__)


DEFAULT_SQLITE_PATH = Path("data/questions.db")
DEFAULT_CHROMA_DIR  = Path("data/chroma")
COLLECTION_NAME     = "questions"


@dataclass
class LoadStats:
    total_in_sqlite: int = 0
    embedded: int = 0            # freshly vectorised this run
    skipped: int = 0             # already present in collection
    per_book: dict[str, int] = field(default_factory=dict)
    per_qtype: dict[str, int] = field(default_factory=dict)

    def summary(self) -> str:
        lines = [
            f"  total in SQLite    : {self.total_in_sqlite}",
            f"  newly embedded     : {self.embedded}",
            f"  skipped (existing) : {self.skipped}",
        ]
        if self.per_book:
            lines.append("  per book (newly embedded):")
            for b, n in sorted(self.per_book.items()):
                lines.append(f"    {b:24s} {n}")
        if self.per_qtype:
            lines.append("  per question_type (newly embedded):")
            for qt, n in sorted(self.per_qtype.items()):
                lines.append(f"    {qt:22s} {n}")
        return "\n".join(lines)


def _load_kp_index(conn: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    """kp_id → row dict, used by build_embedding_text to look up 中文 names."""
    idx: dict[str, dict[str, Any]] = {}
    for row in conn.execute("SELECT id, level1, level2, aliases_json FROM knowledge_points"):
        idx[row["id"]] = {
            "id":      row["id"],
            "level1":  row["level1"],
            "level2":  row["level2"],
            "aliases": json.loads(row["aliases_json"]),
        }
    return idx


def _load_all_questions(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Return every question in the shape build_embedding_text expects.

    We deserialise `options_json` back to a list; `answer_json` is not needed
    for embedding text so we skip it. KP ids are joined via the M:N table.
    """
    kp_rows_by_qid: dict[str, list[str]] = {}
    for row in conn.execute(
        "SELECT question_id, knowledge_point_id "
        "FROM question_knowledge_points ORDER BY question_id, knowledge_point_id"
    ):
        kp_rows_by_qid.setdefault(row["question_id"], []).append(row["knowledge_point_id"])

    out: list[dict[str, Any]] = []
    q_rows = conn.execute(
        """
        SELECT id, book, question_type, chapter_l1, chapter_l2, number,
               stem, options_json, hint,
               original_sentence, instruction, template
        FROM questions
        ORDER BY id
        """
    )
    for r in q_rows:
        out.append({
            "id":                r["id"],
            "book":              r["book"],
            "question_type":     r["question_type"],
            "chapter_l1":        r["chapter_l1"],
            "chapter_l2":        r["chapter_l2"],
            "number":            r["number"],
            "stem":              r["stem"],
            "options":           json.loads(r["options_json"]) if r["options_json"] else None,
            "hint":              r["hint"],
            "original_sentence": r["original_sentence"],
            "instruction":       r["instruction"],
            "template":          r["template"],
            "knowledge_point_ids": kp_rows_by_qid.get(r["id"], []),
        })
    return out


def _build_metadata(q: dict[str, Any]) -> dict[str, str]:
    """ChromaDB metadata values must be scalar (str/int/float/bool).
    List of KP ids is joined by comma — Retriever will split back."""
    return {
        "question_type": q["question_type"],
        "book":          q["book"],
        "chapter_l1":    q["chapter_l1"],
        "chapter_l2":    q["chapter_l2"],
        "kp_ids":        ",".join(q["knowledge_point_ids"]),
    }


def load(
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    chroma_dir:  Path = DEFAULT_CHROMA_DIR,
    embedder_cfg: EmbedderConfig | None = None,
) -> LoadStats:
    """Populate ChromaDB `questions` collection from the SQLite question bank."""
    import chromadb                                # lazy — heavy client init

    if not sqlite_path.is_file():
        raise FileNotFoundError(f"SQLite DB not found: {sqlite_path}")

    chroma_dir.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(chroma_dir))
    # metadata={"hnsw:space": "cosine"} pins the distance metric to match
    # the L2-normalised vectors we hand it (see embedder.py). Passing the
    # metadata on `get_or_create` is idempotent — if the collection was made
    # before with a different space, ChromaDB will refuse and surface the
    # mismatch loudly.
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    # ─ 1. See which ids already have a vector; skip them ─
    already_have: set[str] = set()
    if collection.count() > 0:
        # ChromaDB has no "get all ids" call; page through in one shot.
        page = collection.get(include=[])
        already_have = set(page.get("ids", []))
    log.info("collection currently holds %d vectors", len(already_have))

    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row
    try:
        kp_index    = _load_kp_index(conn)
        all_qs      = _load_all_questions(conn)
    finally:
        conn.close()

    stats = LoadStats(total_in_sqlite=len(all_qs))
    stats.skipped = sum(1 for q in all_qs if q["id"] in already_have)

    to_embed = [
        q for q in all_qs
        if q["id"] not in already_have
        and q["question_type"] != "listening_true_false"   # TF passage 题不做向量库
    ]
    if not to_embed:
        log.info("nothing to do — all %d questions already embedded", stats.total_in_sqlite)
        return stats

    # ─ 2. Build the parallel arrays ChromaDB wants ─
    ids        = [q["id"] for q in to_embed]
    documents  = [build_embedding_text(q, kp_index) for q in to_embed]
    metadatas  = [_build_metadata(q) for q in to_embed]

    # ─ 3. Encode all documents ─
    embedder = QwenEmbedder(embedder_cfg)
    log.info("embedding %d question(s) with dim=%d", len(documents), embedder.dim)
    embeddings = embedder.embed(documents)

    # ─ 4. Bulk write. ChromaDB handles arbitrary length internally. ─
    collection.add(
        ids=ids,
        documents=documents,
        metadatas=metadatas,
        embeddings=embeddings,
    )
    stats.embedded = len(to_embed)
    for q in to_embed:
        stats.per_book[q["book"]] = stats.per_book.get(q["book"], 0) + 1
        stats.per_qtype[q["question_type"]] = stats.per_qtype.get(q["question_type"], 0) + 1

    log.info("committed %d vectors", stats.embedded)
    return stats


# ─── Search helper (Spec §3.8 preview — kept trivial; a real Retriever lives
# in Spec B / ai_engine/) ────────────────────────────────────────────────────

def search(
    query: str,
    n_results: int = 5,
    *,
    question_type: str | None = None,
    book: str | None = None,
    chroma_dir: Path = DEFAULT_CHROMA_DIR,
    embedder_cfg: EmbedderConfig | None = None,
) -> list[dict[str, Any]]:
    """One-shot cosine-similarity search — used by the CLI `search-vec` command
    to sanity-check the collection after building it. NOT the AI Engine's
    Retriever (that one will do KP filtering, revision, etc.).

    Filters: pass `question_type`/`book` to ChromaDB as a `where=` clause.
    """
    import chromadb

    client = chromadb.PersistentClient(path=str(chroma_dir))
    collection = client.get_collection(COLLECTION_NAME)

    embedder = QwenEmbedder(embedder_cfg)
    query_vec = embedder.embed([query])[0]

    where: dict[str, Any] | None = None
    conds = {k: v for k, v in {"question_type": question_type, "book": book}.items() if v}
    if conds:
        where = conds if len(conds) == 1 else {"$and": [{k: v} for k, v in conds.items()]}

    res = collection.query(
        query_embeddings=[query_vec],
        n_results=n_results,
        where=where,
        include=["documents", "metadatas", "distances"],
    )

    # Query results are wrapped in a single-batch outer list; flatten it.
    hits: list[dict[str, Any]] = []
    for i, qid in enumerate(res["ids"][0]):
        hits.append({
            "id":       qid,
            "distance": res["distances"][0][i],
            "metadata": res["metadatas"][0][i],
            "document": res["documents"][0][i],
        })
    return hits
