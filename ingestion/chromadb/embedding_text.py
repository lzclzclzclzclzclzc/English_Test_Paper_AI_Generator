"""Build the text a question gets encoded from (Spec §2.5).

Not stored in SQLite — regenerated at ChromaDB load time (or wherever a
downstream needs it) so the main DB stays free of derived text.

The template is deliberately labelled with 中文 field markers so Qwen picks
up both attributes ([题型]/[考点]) and content ([题干]/...). Downstream
retrieval builds its query text using the same labels.

Rules (Spec §2.5, adjusted 2026-07-09):
  * no `[难度]` line — difficulty was dropped
  * multiple KPs render as multiple `[考点]` lines, not concatenated
  * `<u>...</u>` underline tags in `original_sentence` are stripped (models
    do not parse HTML; keeping the words alone is what matters)
  * blank placeholders (`___`, long underscores) are kept verbatim
"""
from __future__ import annotations

import re
from typing import Any

# ─── level1 slug → 中文 label used in the template ──────────────────
QTYPE_LABEL = {
    "single_choice":       "单项选择",
    "word_form":           "词性转换",
    "sentence_rewriting":  "改写句子",
    "listening_single_choice": "听力选择",
    "listening_fill_blank":    "听力填词",
}

# The <u>...</u> tags are inserted by us in stage 3 (see §3.11); strip them
# before embedding — Qwen would just tokenise `<u>` as noise.
_U_TAG_RE = re.compile(r"</?u>")


def _clean(text: str | None) -> str:
    """Strip <u> markup and collapse trailing whitespace. Empty in → empty out."""
    if not text:
        return ""
    return _U_TAG_RE.sub("", text).strip()


def build_embedding_text(question: dict, kp_index: dict[str, dict]) -> str:
    """Return the embedding_text for one question.

    Parameters
    ----------
    question : dict
        A row from `data/chapters/<book>.json` (or from the SQLite `questions`
        table with `options` / `answer` deserialised). Only the fields listed
        in §2.5 are read.
    kp_index : dict[kp_id → {"level2": str, ...}]
        Lookup table for turning `knowledge_point_ids` into 中文 KP names.

    Output
    ------
    A multi-line string following the §2.5 template. No trailing newline.
    """
    qt = question["question_type"]
    lines: list[str] = []
    lines.append(f"[题型] {QTYPE_LABEL[qt]}")

    # 多 KP → 多行 (§2.5)
    for kp_id in question.get("knowledge_point_ids", []) or []:
        kp = kp_index.get(kp_id)
        if kp is None:
            continue          # dangling reference; skip silently (rare)
        lines.append(f"[考点] {kp['level2']}")

    if qt == "single_choice" or qt == "listening_single_choice":
        lines.append(f"[题干] {_clean(question.get('stem'))}")
        options = question.get("options") or []
        options_str = "  ".join(
            f"{o['label']}) {o['text']}" for o in options
        )
        lines.append(f"[选项] {options_str}")

    elif qt == "word_form":
        hint = _clean(question.get("hint"))
        if hint:
            lines.append(f"[提示] {hint}")
        lines.append(f"[题干] {_clean(question.get('stem'))}")

    elif qt == "sentence_rewriting":
        original = _clean(question.get("original_sentence"))
        if original:
            # 连词成句 puts the token bag in `original_sentence` — same field.
            label = "[词组]" if question.get("template") is None else "[原句]"
            lines.append(f"{label} {original}")
        instruction = _clean(question.get("instruction"))
        if instruction:
            lines.append(f"[要求] {instruction}")
        template = _clean(question.get("template"))
        if template:
            lines.append(f"[模板] {template}")

    elif qt == "listening_fill_blank":
        stem = _clean(question.get("stem"))
        if stem:
            lines.append(f"[题干] {stem}")

    else:
        raise ValueError(f"unknown question_type: {qt!r}")

    return "\n".join(lines)
