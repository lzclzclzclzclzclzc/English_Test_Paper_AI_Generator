"""Stage 3b: apply the frozen knowledge tree to per-book chapters JSON.

Reads:
    data/kb/knowledge_tree.json          — reviewer-approved KP list + mapping
    data/chapters/<book>.json            — chapter_splitter output (RawQuestion list)

Writes:
    data/chapters/<book>.json in place — each question gains
        `knowledge_point_ids`: list[str]

Deterministic, no LLM. Lookup key = "<question_type> / <chapter_l1> / <chapter_l2>".
Idempotent: rerunning produces identical JSON (byte-for-byte, module ordering).

Also performs post-run validation:
  * every question has at least one KP  (or the mapping is missing → warning)
  * every referenced kp_id exists in knowledge_tree
  * every KP's level1 matches the question's question_type
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from collections import Counter

log = logging.getLogger(__name__)


DEFAULT_TREE_PATH   = Path("data/kb/knowledge_tree.json")
DEFAULT_CHAPTERS    = Path("data/chapters")


@dataclass
class ApplyStats:
    total_questions: int = 0
    written: int = 0
    already_correct: int = 0     # rerun: field already present with same value
    missing_mapping: list[str] = field(default_factory=list)  # chapter keys not in tree
    per_kp_count: Counter = field(default_factory=Counter)

    def format(self) -> str:
        lines = [
            f"  total questions:      {self.total_questions}",
            f"  wrote KP ids:         {self.written}",
            f"  already up-to-date:   {self.already_correct}",
            f"  missing mappings:     {len(self.missing_mapping)}",
        ]
        if self.missing_mapping:
            for k in sorted(set(self.missing_mapping))[:10]:
                lines.append(f"    ✗ {k}")
        return "\n".join(lines)


def load_tree(path: Path) -> tuple[dict[str, str], dict[str, list[str]]]:
    """Load knowledge_tree.json. Returns (kp_id → level1, chapter_key → [kp_id, ...])."""
    tree = json.loads(path.read_text(encoding="utf-8"))
    kp_level1 = {k["id"]: k["level1"] for k in tree["knowledge_points"]}
    mapping   = tree["chapter_to_kp"]

    # Sanity: every mapping target must exist as a KP.
    for src, targets in mapping.items():
        for t in targets:
            if t not in kp_level1:
                raise ValueError(f"chapter_to_kp references unknown kp_id: {src!r} → {t!r}")

    return kp_level1, mapping


def apply_to_book(
    book_json: Path,
    kp_level1: dict[str, str],
    mapping: dict[str, list[str]],
    stats: ApplyStats,
) -> None:
    """Rewrite one book's chapters JSON with `knowledge_point_ids` filled in."""
    data = json.loads(book_json.read_text(encoding="utf-8"))

    for q in data:
        stats.total_questions += 1
        key = f"{q['question_type']} / {q['chapter_l1']} / {q['chapter_l2']}"
        kp_ids = mapping.get(key)

        if kp_ids is None:
            # Chapter has no mapping — leave field empty, but log so we notice.
            new_value: list[str] = []
            stats.missing_mapping.append(key)
        else:
            # Freeze order to match tree order (deterministic output).
            new_value = list(kp_ids)

        # Post-checks per KP.
        for kp_id in new_value:
            level1 = kp_level1[kp_id]
            if level1 != q["question_type"]:
                raise ValueError(
                    f"level1 mismatch at {book_json.name} {q['chapter_l2']}/{q['number']}: "
                    f"question_type={q['question_type']!r} but kp {kp_id!r}.level1={level1!r}"
                )
            stats.per_kp_count[kp_id] += 1

        if q.get("knowledge_point_ids") == new_value:
            stats.already_correct += 1
        else:
            q["knowledge_point_ids"] = new_value
            stats.written += 1

    book_json.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def apply_all(
    tree_path: Path = DEFAULT_TREE_PATH,
    chapters_dir: Path = DEFAULT_CHAPTERS,
) -> ApplyStats:
    """Apply the tree to every *.json under chapters_dir."""
    kp_level1, mapping = load_tree(tree_path)
    stats = ApplyStats()

    for book_json in sorted(chapters_dir.glob("*.json")):
        apply_to_book(book_json, kp_level1, mapping, stats)

    return stats
