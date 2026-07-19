"""End-to-end demo: attempt history → mastery profile → review-mode paper.

Seeds a synthetic answer history for one demo user (some KPs deliberately
weak), then runs the full review pipeline and writes a Markdown report
showing the injected distribution, the Analyzer's profile, and the final paper.

Usage
-----
    PYTHONIOENCODING=utf-8 python tests/scripts/review_flow_report.py

Output: tests/scripts/review_flow_report_<YYYYMMDD_HHMMSS>.md

Note: this WRITES to data/questions.db (attempts / attempt_items tables).
That file is under `git update-index --skip-worktree`, so the writes won't
show up in `git status`. The demo user's rows are cleared and re-seeded on
each run, so it's idempotent.
"""
from __future__ import annotations

import json
import random
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from ai_engine import analyzer, parser, retriever, reviser
from shared.config import get_config
from shared.schemas import PaperItem

USER_ID = "u_demo_review"
SEED = 42

# KP → (target accuracy, number of attempts). Low-accuracy KPs are the ones
# we expect the Analyzer to surface as weak. A mix of sample sizes lets us see
# Wilson's low-sample down-weighting in action.
KP_PLAN: list[tuple[str, float, int]] = [
    # --- deliberately WEAK knowledge points ---
    ("kp_sc_verbs",           0.20, 20),   # big sample, low accuracy
    ("kp_sc_prepositions",    0.25, 16),
    ("kp_sr_passive_voice",   0.15, 12),
    ("kp_wf_verb_to_noun",    0.30, 10),
    # --- borderline / medium ---
    ("kp_sc_adverb",          0.55, 14),
    ("kp_sc_articles",        0.50, 8),
    ("kp_sc_modal_verbs",     0.60, 10),
    # --- strong knowledge points ---
    ("kp_sc_adjective",       0.85, 18),
    ("kp_sc_communication",   0.80, 15),
    ("kp_sc_indef_pronoun",   0.90, 12),
    ("kp_sr_word_ordering",   0.85, 10),
    ("kp_wf_noun_plural",     0.75, 8),
]


# ---------------------------------------------------------------------------
# Seeding
# ---------------------------------------------------------------------------

def _kp_to_type(kp_id: str) -> str:
    if kp_id.startswith("kp_sc_"):
        return "single_choice"
    if kp_id.startswith("kp_wf_"):
        return "word_form"
    return "sentence_rewriting"


def _pick_source_questions(conn: sqlite3.Connection, kp_id: str, n: int) -> list[str]:
    """Grab up to n distinct real question ids carrying this KP. If the KP has
    fewer than n questions, cycle through what's available (source ids only
    need to be plausible, not unique across attempts — but the table has a
    UNIQUE(attempt_id, source_question_id) constraint, so callers must spread
    duplicates across multiple attempts)."""
    rows = conn.execute(
        """
        SELECT q.id FROM questions q
        JOIN question_knowledge_points qk ON q.id = qk.question_id
        WHERE qk.knowledge_point_id = ?
        ORDER BY q.id
        """,
        (kp_id,),
    ).fetchall()
    ids = [r[0] for r in rows] or ["q_unknown"]
    return ids


def seed_history(db_path: str, rng: random.Random) -> list[dict]:
    """Wipe + re-seed the demo user's attempt history. Returns the per-KP
    injected summary for the report.

    attempt_items has UNIQUE(attempt_id, source_question_id); to record N
    answers for a KP we distribute them across enough attempts that no
    (attempt, question) pair repeats."""
    conn = sqlite3.connect(db_path)
    try:
        # clear previous demo rows (idempotent)
        old = conn.execute(
            "SELECT id FROM attempts WHERE user_id = ?", (USER_ID,)
        ).fetchall()
        old_ids = [r[0] for r in old]
        if old_ids:
            ph = ",".join("?" * len(old_ids))
            conn.execute(f"DELETE FROM attempt_items WHERE attempt_id IN ({ph})", old_ids)
            conn.execute("DELETE FROM attempts WHERE user_id = ?", (USER_ID,))

        base = int(time.time())
        # Build a set of attempt rows lazily; each (attempt, question) pair
        # must be unique. We keep a per-attempt set of used question ids.
        attempt_used: dict[str, set[str]] = {}

        def _new_attempt(seq: int) -> str:
            aid = f"att_{USER_ID}_{base}_{seq}"
            conn.execute(
                "INSERT INTO attempts (id, user_id, paper_id, answered_at) "
                "VALUES (?, ?, 'p_demo', datetime('now'))",
                (aid, USER_ID),
            )
            attempt_used[aid] = set()
            return aid

        attempts_pool = [_new_attempt(i) for i in range(3)]  # start with 3

        summary: list[dict] = []
        for kp_id, target_acc, n in KP_PLAN:
            qtype = _kp_to_type(kp_id)
            source_ids = _pick_source_questions(conn, kp_id, n)
            correct = 0
            for i in range(n):
                source_id = source_ids[i % len(source_ids)]
                # find an attempt that hasn't used this source_id yet
                aid = None
                for candidate in attempts_pool:
                    if source_id not in attempt_used[candidate]:
                        aid = candidate
                        break
                if aid is None:  # all attempts used this question → new attempt
                    aid = _new_attempt(len(attempts_pool))
                    attempts_pool.append(aid)

                is_correct = 1 if rng.random() < target_acc else 0
                correct += is_correct
                conn.execute(
                    "INSERT INTO attempt_items "
                    "(attempt_id, source_question_id, question_type, is_correct, kps_json) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (aid, source_id, qtype, is_correct, json.dumps([kp_id])),
                )
                attempt_used[aid].add(source_id)
            summary.append({
                "kp_id": kp_id,
                "qtype": qtype,
                "attempts": n,
                "correct": correct,
                "accuracy": correct / n,
                "target": target_acc,
            })
        conn.commit()
        return summary
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------

def _fmt_answer(answer) -> str:
    if isinstance(answer, str):
        return answer
    groups = []
    for g in answer:
        groups.append("  ".join(f"{k}: {' / '.join(v)}" for k, v in g.items()))
    return " 或 ".join(groups)


def _render_question(item: PaperItem) -> str:
    q = item.question
    lines = [
        f"**{item.index}.** `{q.question_type}` | KP: `{'`, `'.join(q.knowledge_point_ids)}`"
        f"  ← 源题 `{item.source_question_id}` (`{item.revision_mode}`)"
    ]
    if q.stem:
        lines.append(f"> {q.stem}")
    if q.original_sentence:
        lines.append(f"> 原句: {q.original_sentence}")
    if q.instruction:
        lines.append(f"> 要求: {q.instruction}")
    if q.template:
        lines.append(f"> 模板: `{q.template}`")
    if q.hint:
        lines.append(f"> 提示词: _{q.hint}_")
    if q.options:
        for o in q.options:
            lines.append(f"> - **{o.label}.** {o.text}")
    lines.append(f"> **答案:** {_fmt_answer(q.answer)}")
    return "\n".join(lines)


def build_report(summary, profile, req, paper, timings) -> str:
    weak_ids = {k.knowledge_point_id for k in profile.weak_kps}
    L: list[str] = []
    L.append("# Review 全流程演示报告")
    L.append("")
    L.append(f"**用户**: `{USER_ID}`  ")
    L.append(f"**随机种子**: {SEED}  ")
    L.append(f"**总耗时**: {timings['total']:.1f}s "
             f"(Analyzer {timings['analyzer']:.2f}s / Parser {timings['parser']:.2f}s / "
             f"Retriever {timings['retriever']:.2f}s / Reviser {timings['reviser']:.2f}s)  ")
    L.append("")

    # 1. injected history
    L.append("## ① 注入的历史做题分布")
    L.append("")
    L.append("按正确率升序排列。⚠️ 标记的是预设的薄弱知识点。")
    L.append("")
    L.append("| 知识点 | 题型 | 做题数 | 正确 | 正确率 | Analyzer 判定薄弱 |")
    L.append("|--------|------|--------|------|--------|:---:|")
    for s in sorted(summary, key=lambda x: x["accuracy"]):
        weak_mark = "✅ 是" if s["kp_id"] in weak_ids else ""
        L.append(
            f"| `{s['kp_id']}` | {s['qtype']} | {s['attempts']} | {s['correct']} "
            f"| {s['accuracy']*100:.0f}% | {weak_mark} |"
        )
    L.append("")

    # 2. mastery profile
    L.append("## ② Analyzer 掌握度画像（MasteryProfile）")
    L.append("")
    L.append(f"- `total_attempts_considered`: **{profile.total_attempts_considered}**")
    L.append(f"- `dominant_types`（错题最多的题型）: `{profile.dominant_types}`")
    L.append("")
    L.append("`weak_kps`（按 Wilson 掌握度升序，最薄弱在前）:")
    L.append("")
    L.append("| 排名 | 知识点 | 做题数 | mastery (Wilson) |")
    L.append("|:----:|--------|--------|------------------|")
    for i, k in enumerate(profile.weak_kps, 1):
        L.append(f"| {i} | `{k.knowledge_point_id}` | {k.attempts} | {k.mastery:.3f} |")
    L.append("")

    # 3. parser output
    L.append("## ③ Parser 解析结果（review 模式）")
    L.append("")
    L.append("| 字段 | 值 |")
    L.append("|------|-----|")
    L.append(f"| mode | `{req.mode}` |")
    L.append(f"| total_questions | {req.total_questions} |")
    L.append(f"| knowledge_points | `{req.knowledge_points}` |")
    L.append(f"| question_types | `{req.question_types or '(不限)'}` |")
    L.append(f"| type_distribution | `{req.type_distribution or '{}'}` |")
    L.append(f"| revision_intensity | `{req.revision_intensity}` |")
    L.append(f"| free_text | `{req.free_text!r}` |")
    L.append("")
    # coverage check: how many of the paper's KPs were weak ones
    L.append("**针对性校验**：Parser 选中的知识点里，属于薄弱项的有：")
    hit = [kp for kp in req.knowledge_points if kp in weak_ids]
    L.append(f"`{hit}`（{len(hit)}/{len(req.knowledge_points)}）")
    L.append("")

    # 4. paper
    L.append(f"## ④ 生成的试卷 — {paper.title}")
    L.append("")
    L.append(f"共 **{len(paper.items)}** 道题 | LLM 调用 **{paper.metadata.get('llm_calls')}** 次"
             f" | 改题档位 `{req.revision_intensity}`")
    if paper.metadata.get("revision_failures"):
        L.append(f" | ⚠️ fallback 题号: {paper.metadata['revision_failures']}")
    if paper.metadata.get("shortfall"):
        L.append(f" | ⚠️ 缺口: {paper.metadata['shortfall']}")
    L.append("")
    for item in paper.items:
        L.append(_render_question(item))
        L.append("")

    return "\n".join(L)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    rng = random.Random(SEED)
    cfg = get_config()
    db_path = str(cfg.db_path)

    print("=" * 60)
    print("  Review 全流程演示")
    print("=" * 60)

    print("  [1/5] 注入历史做题记录 ...", end="", flush=True)
    summary = seed_history(db_path, rng)
    print(f" ✓  {len(summary)} 个知识点")

    t = {}
    t0 = time.time()

    print("  [2/5] Analyzer 构建掌握度画像 ...", end="", flush=True)
    ta = time.time()
    profile = analyzer.build_profile(USER_ID, window_days=30)
    t["analyzer"] = time.time() - ta
    print(f" ✓  {t['analyzer']:.2f}s  → weak_kps={len(profile.weak_kps)}")

    print("  [3/5] Parser 解析（review 模式）...", end="", flush=True)
    tp = time.time()
    req = parser.parse("帮我复习一下最近的薄弱知识点，出10道题",
                       mode="review", mastery=profile)
    req.user_id = USER_ID
    req.review_window_days = 30
    t["parser"] = time.time() - tp
    print(f" ✓  {t['parser']:.2f}s  → KP={req.knowledge_points}")

    print("  [4/5] Retriever 检索 ...", end="", flush=True)
    tr = time.time()
    retrieval = retriever.retrieve(req)
    t["retriever"] = time.time() - tr
    print(f" ✓  {t['retriever']:.2f}s  → 候选 {len(retrieval.items)} 题")

    print("  [5/5] Reviser 生成试卷 ...", end="", flush=True)
    tv = time.time()
    paper = reviser.build_paper(req, retrieval)
    t["reviser"] = time.time() - tv
    print(f" ✓  {t['reviser']:.2f}s")

    t["total"] = time.time() - t0

    report = build_report(summary, profile, req, paper, t)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = Path(__file__).parent / f"review_flow_report_{ts}.md"
    out.write_text(report, encoding="utf-8")

    print(f"\n{'=' * 60}")
    print(f"  完成，报告: {out}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
