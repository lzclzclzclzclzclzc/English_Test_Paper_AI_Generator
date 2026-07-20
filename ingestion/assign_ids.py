"""Stage 3c: assign stable, globally-monotonic ids to every question.

Reads/writes:
    data/chapters/<book>.json                — chapter_splitter output

Adds a top-level `id` field (`q_00001`..`q_NNNNN`) to each question.
Runs deterministically across books:

    Sort key = (book, question_type, chapter_l2 numeric, number numeric)

with these total orders:

    book:          shanghai_2021_yimo  <  shanghai_2021_ermo
    question_type: single_choice < word_form < sentence_rewriting
    chapter_l2:    "1.1" < "1.2" < "1.10" (numeric, not lexicographic)
    number:        "1" < "1-1" < "1-2" < "2" (main-then-variant)

Idempotency:
    Spec § 2.7 guarantees `Question.id` is immutable once assigned. Rerunning
    this command preserves every already-present id — only questions missing
    an `id` get one, and only from the pool of ids not already in use.
    That way it's safe to run repeatedly as new books are added.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path


BOOK_ORDER: dict[str, int] = {
    "shanghai_2021_yimo": 0,
    "shanghai_2021_ermo": 1,
}

QTYPE_ORDER: dict[str, int] = {
    "single_choice": 0,
    "word_form": 1,
    "sentence_rewriting": 2,
}


def _l2_key(chapter_l2: str) -> tuple[int, int]:
    """'1.1 语音' → (1, 1); '1.24 其他' → (1, 24). Fails loudly if the prefix
    doesn't match — sorting depends on numeric ordering across all books."""
    m = re.match(r"(\d+)\.(\d+)", chapter_l2)
    if not m:
        raise ValueError(f"chapter_l2 has no numeric prefix: {chapter_l2!r}")
    return (int(m.group(1)), int(m.group(2)))


def _number_key(number: str) -> tuple[int, int]:
    """'1' → (1, 0); '1-1' → (1, 1); '11-3' → (11, 3).

    Main questions sort BEFORE their variants (variant tail 0 vs ≥1).
    `chapter_splitter` normalizes full-width `－` to half-width `-` upstream,
    so we only see `-` here."""
    if "-" in number:
        head, tail = number.split("-", 1)
        return (int(head), int(tail))
    return (int(number), 0)


def _sort_key(q: dict) -> tuple:
    if q["book"] not in BOOK_ORDER:
        raise ValueError(f"unknown book (needs to be added to BOOK_ORDER): {q['book']!r}")
    return (
        BOOK_ORDER[q["book"]],
        QTYPE_ORDER[q["question_type"]],
        _l2_key(q["chapter_l2"]),
        _number_key(q["number"]),
    )


@dataclass
class AssignStats:
    total: int = 0
    preserved: int = 0     # already had an id, kept as-is
    assigned: int = 0      # got a new id this run
    per_book: dict[str, tuple[str, str]] = field(default_factory=dict)
    # per_book[slug] = (min_id, max_id)


def _load_all(chapters_dir: Path) -> list[tuple[Path, list[dict]]]:
    """Return [(path, questions), ...] sorted by BOOK_ORDER."""
    entries: list[tuple[Path, list[dict]]] = []
    for path in sorted(chapters_dir.glob("*.json"), key=lambda p: BOOK_ORDER.get(p.stem, 999)):
        data = json.loads(path.read_text(encoding="utf-8"))
        entries.append((path, data))
    return entries


def _with_id_first(q: dict) -> dict:
    """Move `id` to the first field for readability. Preserves all other order."""
    if "id" not in q:
        return q
    return {"id": q["id"], **{k: v for k, v in q.items() if k != "id"}}


def assign_ids(chapters_dir: Path = Path("data/chapters")) -> AssignStats:
    """Idempotent: existing ids stay, missing ones get the next unused number."""
    stats = AssignStats()
    entries = _load_all(chapters_dir)
    if not entries:
        return stats

    # Flat view for consistent sorting across books.
    all_qs: list[dict] = []
    for _, qs in entries:
        all_qs.extend(qs)
    all_qs.sort(key=_sort_key)
    stats.total = len(all_qs)

    used_numbers: set[int] = set()
    for q in all_qs:
        if "id" in q:
            m = re.match(r"^q_(\d+)$", q["id"])
            if not m:
                raise ValueError(f"non-standard id encountered (won't overwrite): {q['id']!r}")
            used_numbers.add(int(m.group(1)))

    def _next_free() -> int:
        """Smallest positive integer not in `used_numbers`, then record it."""
        i = 1
        while i in used_numbers:
            i += 1
        used_numbers.add(i)
        return i

    for q in all_qs:
        if "id" in q:
            stats.preserved += 1
            continue
        q["id"] = f"q_{_next_free():05d}"
        stats.assigned += 1

    # Verify uniqueness (defensive — a malformed input pool would be caught here).
    ids = [q["id"] for q in all_qs]
    if len(set(ids)) != len(ids):
        raise RuntimeError("assigned ids are not unique — refusing to write")

    # Write back per-book. Preserve sort order within each file.
    for path, _ in entries:
        book_slug = path.stem
        book_qs = sorted(
            (q for q in all_qs if q["book"] == book_slug),
            key=_sort_key,
        )
        path.write_text(
            json.dumps([_with_id_first(q) for q in book_qs], ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        if book_qs:
            stats.per_book[book_slug] = (book_qs[0]["id"], book_qs[-1]["id"])

    return stats
