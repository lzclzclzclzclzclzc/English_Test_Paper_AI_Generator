"""Seed one realistic, fully-inspectable learner (`zecheng`) into an existing DB.

Unlike scripts/seed_acceptance_demo.py (which fabricates papers directly), this
account is built by driving the REAL question-selection + revision pipeline in
its deterministic, no-LLM branch:

    Retriever(free_text="")  → SQL random path  (no vector / no Qwen)
    Reviser(revision_intensity="original")       (copies questions, no LLM)

so every paper is composed of genuine bank questions. Objective answers are
graded through the REAL grading (`backend.services.grading.compare`) at a
controlled ~90% accuracy. The mock exam's writing question is graded by the
REAL LLM writing grader (`ai_engine.writing_grader.grade_writing`) — the essay
text is authored here, the score/level/analysis come from the model.

Writes into an existing app DB (default: data/acceptance-demo.db). It deletes
any pre-existing `zecheng` (including one registered through the app, whose id
is a uuid) and recreates the account fresh with a 2026-08-01 join date, without
touching other accounts.

    python scripts/seed_zecheng.py
    python scripts/seed_zecheng.py --verify
"""
from __future__ import annotations

import argparse
import json
import random
import sqlite3
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai_engine.question_repo import QuestionRepo
from ai_engine.reviser import build_paper
from ai_engine.retriever import Retriever
from ai_engine.writing_grader import grade_writing
from backend.auth.password import hash_password
from backend.schemas import StoredAttempt, StoredAttemptItem
from backend.services.credits.pricing import PRICES, price
from backend.services.grading import _normalize_candidates, compare
from shared import storage
from shared.schemas import GenerateRequest, PaperItem, RevisedQuestion

USERNAME = "zecheng"
PASSWORD = "123456"
DEFAULT_DB = ROOT / "data" / "acceptance-demo.db"
BANK_DB = ROOT / "data" / "questions.db"
START, END = date(2026, 8, 1), date(2026, 8, 30)      # 30 days inclusive
RNG_SEED = 20260801
ACCURACY = 0.90
NEW_PER_DAY, REVIEW_PER_DAY = 20, 10
VOCAB_INTERVALS = (1, 3, 7, 14, 30)

# One objective-focused type mix per day (rotated across the 30 days). Passage
# types (cloze / reading / listening groups) are retrieved whole, so the actual
# question count may differ slightly from the requested total — that's fine, the
# attempt adapts to whatever the paper ends up holding.
DAILY_MIXES: list[tuple[str, dict[str, int]]] = [
    ("单项选择专项", {"single_choice": 6}),
    ("词形转换专项", {"word_form": 6}),
    ("句型转换专项", {"sentence_rewriting": 6}),
    ("选择 + 词形综合", {"single_choice": 3, "word_form": 3}),
    ("完形填空专项", {"cloze_single_choice": 6}),
    ("阅读理解专项", {"reading_longtext_single_choice": 5}),
    ("听力选择专项", {"listening_single_choice": 6}),
    ("听力判断专项", {"listening_true_false": 6}),
    ("听力填词专项", {"listening_fill_blank": 6}),
    ("首字母填空专项", {"reading_first_blank": 6}),
]

# The full-subject mock: one of (almost) everything objective. The writing task
# is appended separately (a fixed prompt + matching essay) so the REAL LLM grade
# is coherent rather than penalising an off-topic random prompt.
MOCK_MIX: dict[str, int] = {
    "single_choice": 4, "word_form": 2, "sentence_rewriting": 2,
    "cloze_single_choice": 3, "reading_longtext_single_choice": 3,
    "listening_single_choice": 2, "listening_true_false": 2,
    "listening_fill_blank": 2, "reading_first_blank": 2,
}

# Deterministic writing prompt for the mock + an on-topic student essay. The
# essay is graded by the REAL LLM writing grader (three dimensions + comment).
WRITING_QUESTION_ID = "q_30008"   # "The power of teamwork"
MOCK_ESSAY = (
    "Last term our class took part in a science project competition. At first "
    "everyone had different ideas and we argued a lot, so our work went slowly. "
    "Then we decided to divide the tasks: some searched for information, some "
    "designed the poster, and I put our report together. Whenever a member got "
    "stuck, the others helped at once. Working together, we finished the project "
    "two days earlier and won the second prize. This experience showed me the "
    "real power of teamwork. Alone we can do little, but together we can solve "
    "hard problems and achieve much more. From now on, I will listen to others "
    "and cooperate with my classmates."
)

MINDMAPS = [
    ("zecheng-mindmap-tense", "时态复习框架", "时态",
     "# 中考英语时态\n\n- 一般现在时：习惯 / 客观事实\n- 一般过去时：过去动作\n- 现在完成时：have/has + 过去分词\n- 一般将来时：will / be going to\n\n## 易错点\n\n- since / for 与完成时搭配\n- 时间状语决定时态\n- 主谓一致优先判断"),
    ("zecheng-mindmap-writing", "书面表达检查清单", "书面表达",
     "# 书面表达\n\n- 开头：点明主题 / 目的\n- 主体：时间、地点、事件、感受\n- 结尾：总结或号召\n\n## 自查\n\n- 时态是否统一\n- 是否使用连接词（first / then / finally）\n- 字数是否达标"),
]


# ── helpers ──────────────────────────────────────────────────────────────────
def ts(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime.combine(day, time(hour, minute), tzinfo=timezone.utc)


def days() -> list[date]:
    return [START + timedelta(days=i) for i in range((END - START).days + 1)]


def kp_name_map() -> dict[str, str]:
    """id → level2 (Chinese name), read from the read-only question bank."""
    with sqlite3.connect(BANK_DB) as conn:
        return {row[0]: row[1] for row in conn.execute("SELECT id, level2 FROM knowledge_points")}


def _placeholder_writing_grade():
    """20-scale fallback used only when the real LLM grader is unreachable."""
    from shared.schemas import WritingGradeResult
    return WritingGradeResult(
        total_score=16.5, content_score=6.6, language_score=6.6, organization_score=3.3,
        word_count=len(MOCK_ESSAY.split()), level="良好",
        content_analysis="内容完整，围绕暑期英语学习计划展开。",
        language_analysis="时态基本准确，可增加高级句式。",
        organization_analysis="结构清晰，首尾呼应。",
        overall_comment="（占位）真实 LLM 批改不可用时的降级评语。",
        revised_version=MOCK_ESSAY,
    )


def build_one_paper(mix: dict[str, int], *, seed: int, total: int | None = None):
    """Drive the real Retriever + Reviser in the deterministic no-LLM branch.

    `total` overrides GenerateRequest.total_questions, which caps how many
    retrieved items build_paper keeps. Passage types are pulled as WHOLE groups
    (a cloze/reading passage is ~6 questions), so they overshoot their per-type
    target; a small total would truncate the tail buckets (e.g. writing). The
    mock passes a large total so every requested type — writing included —
    survives.
    """
    req = GenerateRequest(
        mode="fresh",
        total_questions=total if total is not None else sum(mix.values()),
        question_types=list(mix.keys()),
        type_distribution=mix,
        revision_intensity="original",   # → Reviser copies questions, no LLM
        free_text="",                    # → Retriever SQL random path, no vector
        user_id=USERNAME,
    )
    retrieval = Retriever(db_path=BANK_DB, seed=seed).retrieve(req)
    return build_paper(req, retrieval)


def make_user_answer(question, correct: bool):
    """Produce a user answer that the real grader scores exactly `correct`.

    single-choice family → a letter (correct = the key, wrong = another option);
    fill-in family → a blank→value dict (correct = first candidate, wrong = junk).
    """
    ans = question.answer
    if isinstance(ans, str):
        if correct:
            return ans
        others = [o.label for o in (question.options or []) if o.label.upper() != ans.upper()]
        return others[0] if others else f"{ans}_x"
    if isinstance(ans, list) and ans:
        # Reuse the real candidate-merge so this matches compare() exactly:
        # reading_first_blank merges its per-blank dicts into one all-blanks
        # candidate; other fill-in types keep their first group. A correct
        # answer fills every blank in that group with its first accepted value.
        group = _normalize_candidates(ans)[0]
        if correct:
            return {blank: (cands[0] if cands else "") for blank, cands in group.items()}
        return {blank: "zzz9" for blank in group}
    return None


def attempt_items_for(paper, rng: random.Random) -> list[StoredAttemptItem]:
    """~90% correct across the paper's objective items (writing excluded)."""
    objective = [it for it in paper.items if it.question.question_type != "writing"]
    n = len(objective)
    correct_n = round(ACCURACY * n)
    order = list(range(n))
    rng.shuffle(order)
    correct_idx = set(order[:correct_n])

    items: list[StoredAttemptItem] = []
    for pos, it in enumerate(objective):
        want_correct = pos in correct_idx
        user_answer = make_user_answer(it.question, want_correct)
        is_correct = compare(user_answer, it.question.answer, it.question.question_type)
        # sanity: a junk wrong answer must never match; a keyed correct one must.
        if is_correct != want_correct:
            raise RuntimeError(f"grading mismatch on {it.source_question_id} ({it.question.question_type})")
        items.append(StoredAttemptItem(
            index=it.index,
            source_question_id=it.source_question_id,
            knowledge_point_ids=it.question.knowledge_point_ids,
            question_type=it.question.question_type,
            is_correct=is_correct,
            user_answer=user_answer,
        ))
    return items


# ── cleanup / reset ────────────────────────────────────────────────────────
def clear_user(conn: sqlite3.Connection) -> None:
    """Remove any pre-existing `zecheng` — including the one registered through
    the app (whose id is a uuid, not the username) — plus all its child data,
    so the account can be recreated fresh with a controlled id and join date."""
    ids = {row[0] for row in conn.execute("SELECT id FROM users WHERE username=?", (USERNAME,))}
    ids.add(USERNAME)  # also clears data from a previous run of this seed (id == username)
    child = (
        "papers", "study_plans", "writing_grade_results", "mindmaps",
        "vocabulary_settings", "vocabulary_progress", "vocabulary_daily_cards",
        "vocabulary_review_logs", "vocabulary_daily_retry_queue",
        "credit_accounts", "credit_ledger", "orders", "sessions",
    )
    for uid in ids:
        conn.execute(
            "DELETE FROM attempt_items WHERE attempt_id IN (SELECT id FROM attempts WHERE user_id=?)", (uid,))
        for table in ("attempts", *child):
            try:
                conn.execute(f"DELETE FROM {table} WHERE user_id=?", (uid,))
            except sqlite3.OperationalError:
                pass  # table absent in this DB
    conn.execute("DELETE FROM users WHERE username=?", (USERNAME,))


# ── vocabulary (controlled: 20 new + 10 review per day) ──────────────────────
def seed_vocabulary(conn: sqlite3.Connection) -> tuple[int, int]:
    word_ids = [r[0] for r in conn.execute(
        "SELECT id FROM vocabulary_words WHERE is_active=1 ORDER BY id")]
    need = NEW_PER_DAY * len(days())
    if len(word_ids) < need:
        raise RuntimeError(f"not enough active words: need {need}, have {len(word_ids)}")

    conn.execute("INSERT INTO vocabulary_settings (user_id, daily_new_limit) VALUES (?, ?)",
                 (USERNAME, NEW_PER_DAY))
    new_cards = review_cards = 0
    for d, day in enumerate(days()):
        study_date = day.isoformat()
        new_slice = word_ids[d * NEW_PER_DAY:(d + 1) * NEW_PER_DAY]
        for s, w in enumerate(new_slice):
            due = min(END, day + timedelta(days=VOCAB_INTERVALS[0]))
            conn.execute(
                "INSERT OR IGNORE INTO vocabulary_progress "
                "(user_id, word_id, stage, introduced_at, last_reviewed_at, due_at, review_count) "
                "VALUES (?,?,?,?,?,?,?)",
                (USERNAME, w, 1, ts(day, 8).isoformat(), ts(day, 19, s % 60).isoformat(),
                 ts(due, 8).isoformat(), 1))
            conn.execute(
                "INSERT INTO vocabulary_daily_cards (user_id, study_date, word_id, card_type, completed_at) "
                "VALUES (?,?,?,?,?)",
                (USERNAME, study_date, w, "new", ts(day, 19, s % 60).isoformat()))
            conn.execute(
                "INSERT INTO vocabulary_review_logs "
                "(id, user_id, word_id, reviewed_at, spelling_correct, requested_rating, applied_rating, stage_after, next_due_at) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (f"vlog-{USERNAME}-{study_date}-new-{s}", USERNAME, w, ts(day, 19, s % 60).isoformat(),
                 1, "known", "known", 1, ts(due, 8).isoformat()))
            new_cards += 1

        if d == 0:
            continue  # nothing introduced yet to review on day one
        review_slice = word_ids[(d - 1) * NEW_PER_DAY:(d - 1) * NEW_PER_DAY + REVIEW_PER_DAY]
        for s, w in enumerate(review_slice):
            due = min(END, day + timedelta(days=VOCAB_INTERVALS[1]))
            conn.execute(
                "UPDATE vocabulary_progress SET stage=?, last_reviewed_at=?, due_at=?, review_count=review_count+1 "
                "WHERE user_id=? AND word_id=?",
                (2, ts(day, 20, s % 60).isoformat(), ts(due, 8).isoformat(), USERNAME, w))
            conn.execute(
                "INSERT INTO vocabulary_daily_cards (user_id, study_date, word_id, card_type, completed_at) "
                "VALUES (?,?,?,?,?)",
                (USERNAME, study_date, w, "review", ts(day, 20, s % 60).isoformat()))
            conn.execute(
                "INSERT INTO vocabulary_review_logs "
                "(id, user_id, word_id, reviewed_at, spelling_correct, requested_rating, applied_rating, stage_after, next_due_at) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (f"vlog-{USERNAME}-{study_date}-rev-{s}", USERNAME, w, ts(day, 20, s % 60).isoformat(),
                 1, "known", "known", 2, ts(due, 8).isoformat()))
            review_cards += 1
    return new_cards, review_cards


# ── credits (initial grant + realistic spend per generation) ─────────────────
def seed_credits(conn: sqlite3.Connection, spends: list[tuple[datetime, str, int, str, str]]) -> int:
    """spends: (when, action, cost, ref_type, ref_id). Grants enough up front to
    leave a tidy 300-credit balance after all recorded spend."""
    spends = sorted(spends, key=lambda s: s[0])
    total = sum(cost for _, _, cost, _, _ in spends)
    final_balance = 300
    initial = final_balance + total

    conn.execute(
        "INSERT INTO credit_ledger (user_id, delta, bucket, balance_after, kind, ref_type, ref_id, note, created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (USERNAME, initial, "balance", initial, "admin_adjust", "demo_seed",
         f"seed:{USERNAME}", "初始积分", ts(START, 0).isoformat()))
    running = initial
    for when, action, cost, ref_type, ref_id in spends:
        running -= cost
        conn.execute(
            "INSERT INTO credit_ledger (user_id, delta, bucket, balance_after, kind, action, ref_type, ref_id, note, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (USERNAME, -cost, "balance", running, "spend", action, ref_type, ref_id,
             PRICES[action].label, when.isoformat()))
    conn.execute(
        "INSERT INTO credit_accounts (user_id, balance, daily_balance, daily_date, updated_at) VALUES (?,?,?,?,?)",
        (USERNAME, running, 0, END.isoformat(), ts(END, 23, 59).isoformat()))
    return running


# ── main seed ────────────────────────────────────────────────────────────────
def seed(db: Path) -> dict:
    storage.set_db_path(db)
    try:
        storage.init_db()  # idempotent; ensures tables + migrations exist
        with storage.connect() as conn:
            clear_user(conn)  # drop the originally-registered zecheng + any prior seed
            conn.execute(
                "INSERT INTO users (id, username, password_hash, created_at, role, status) VALUES (?,?,?,?,?,?)",
                (USERNAME, USERNAME, hash_password(PASSWORD), ts(START, 8).isoformat(), "user", "active"))

        names = kp_name_map()
        rng = random.Random(RNG_SEED)
        spends: list[tuple[datetime, str, int, str, str]] = []
        plan_days: list[dict] = []
        papers = attempts = 0

        # 30 daily papers, one per study-plan day.
        for i, day in enumerate(days()):
            theme, mix = DAILY_MIXES[i % len(DAILY_MIXES)]
            paper = build_one_paper(mix, seed=RNG_SEED + i)
            paper.paper_id = f"{USERNAME}-paper-{i:03d}"
            paper.generated_at = ts(day, 9)
            paper.title = f"8月{day.day}日 · {theme}"
            paper.metadata.update({"seed": "zecheng", "source": "study_plan", "generation_action": "generate_original"})
            storage.save_paper(paper, USERNAME)
            papers += 1
            spends.append((paper.generated_at, "generate_original",
                           price("generate_original", len(paper.items)), "paper", paper.paper_id))

            attempt = StoredAttempt(user_id=USERNAME, paper_id=paper.paper_id,
                                    answered_at=ts(day, 10, 30), items=attempt_items_for(paper, rng))
            storage.write_attempt_and_mark_paper_submitted(attempt)
            attempts += 1

            kp_ids = sorted({kp for it in paper.items for kp in it.question.knowledge_point_ids})
            plan_days.append({
                "index": i + 1, "date": day.isoformat(), "theme": theme,
                "knowledge_points": kp_ids, "kp_names": [names.get(k, k) for k in kp_ids],
                "question_types": list(mix.keys()), "total_questions": len(paper.items),
                "note": "已完成；根据错题调整下一日复习重点。",
                "paper_id": paper.paper_id, "paper_title": paper.title,
            })

        # Full-subject mock exam: objective全科 via the real pipeline, plus one
        # deterministic writing task appended by hand (fixed prompt + matching
        # essay) so the REAL LLM grade is coherent, not an off-topic random one.
        mock = build_one_paper(MOCK_MIX, seed=RNG_SEED + 999, total=999)  # keep every objective type
        writing_q = QuestionRepo(BANK_DB).get_by_ids([WRITING_QUESTION_ID])[WRITING_QUESTION_ID]
        mock.items.append(PaperItem(
            index=len(mock.items) + 1,
            question=RevisedQuestion.model_validate(writing_q.model_dump()),
            source_question_id=writing_q.id,
            revision_mode="original",
        ))
        mock.request.total_questions = len(mock.items)  # tidy: match the real item count
        mock.paper_id = f"{USERNAME}-mock-000"
        mock.generated_at = ts(END, 15)
        mock.title = "开学前全科模拟卷"
        mock.metadata.update({"seed": "zecheng", "source": "mock", "generation_action": "generate_original"})
        storage.save_paper(mock, USERNAME)
        papers += 1
        spends.append((mock.generated_at, "generate_original", price("generate_original", len(mock.items)), "paper", mock.paper_id))

        mock_attempt = StoredAttempt(user_id=USERNAME, paper_id=mock.paper_id,
                                     answered_at=ts(END, 16), items=attempt_items_for(mock, rng))
        storage.write_attempt_and_mark_paper_submitted(mock_attempt)
        attempts += 1

        # Writing question in the mock → authored essay, REAL LLM grading.
        writing_items = [it for it in mock.items if it.question.question_type == "writing"]
        writing_graded = 0
        for it in writing_items:
            try:
                result = grade_writing(it.question, MOCK_ESSAY)   # real LLM three-dimensional grade
            except Exception as exc:  # network/API failure — don't discard the 30 papers already seeded
                print(f"[warn] real writing grade failed ({exc}); using a 20-scale placeholder", file=sys.stderr)
                result = _placeholder_writing_grade()
            storage.save_writing_attempt_items(USERNAME, mock.paper_id, [{
                "index": it.index, "source_question_id": it.source_question_id,
                "question_type": "writing", "user_essay": MOCK_ESSAY,
                "knowledge_point_ids": it.question.knowledge_point_ids,
            }])
            storage.save_writing_grade_results(USERNAME, mock.paper_id, [{
                "index": it.index, "user_essay": MOCK_ESSAY,
                "total_score": result.total_score, "content_score": result.content_score,
                "language_score": result.language_score, "organization_score": result.organization_score,
                "word_count": result.word_count, "level": result.level,
                "content_analysis": result.content_analysis, "language_analysis": result.language_analysis,
                "organization_analysis": result.organization_analysis,
                "overall_comment": result.overall_comment, "revised_version": result.revised_version,
            }])
            spends.append((ts(END, 16, 30), "writing_grade", price("writing_grade"), "writing", mock.paper_id))
            writing_graded += 1

        # Study plan spanning all 30 daily papers.
        with storage.connect() as conn:
            conn.execute(
                "INSERT INTO study_plans (id, user_id, created_at, status, total_days, plan_json) VALUES (?,?,?,?,?,?)",
                (f"{USERNAME}-plan", USERNAME, ts(START, 8).isoformat(), "active", len(plan_days),
                 json.dumps({"total_days": len(plan_days), "days": plan_days}, ensure_ascii=False)))

            for mid, title, kp, outline in MINDMAPS:
                when = ts(START + timedelta(days=7), 20).isoformat()
                conn.execute(
                    "INSERT INTO mindmaps (id, user_id, created_at, updated_at, title, knowledge_point, outline_md) "
                    "VALUES (?,?,?,?,?,?,?)",
                    (mid, USERNAME, when, when, title, kp, outline))

            new_cards, review_cards = seed_vocabulary(conn)
            balance = seed_credits(conn, spends)

        return {"user": USERNAME, "papers": papers, "attempts": attempts,
                "writing_graded": writing_graded, "plan_days": len(plan_days),
                "vocab_new": new_cards, "vocab_review": review_cards, "balance": balance}
    finally:
        storage.set_db_path(None)


# ── verify ─────────────────────────────────────────────────────────────────
def verify(db: Path) -> dict:
    conn = sqlite3.connect(db)
    try:
        papers = conn.execute("SELECT COUNT(*) FROM papers WHERE user_id=?", (USERNAME,)).fetchone()[0]
        submitted = conn.execute("SELECT COUNT(*) FROM papers WHERE user_id=? AND submitted=1", (USERNAME,)).fetchone()[0]
        row = conn.execute(
            "SELECT SUM(is_correct), COUNT(*) FROM attempt_items ai "
            "JOIN attempts a ON a.id=ai.attempt_id WHERE a.user_id=? AND ai.question_type<>'writing'",
            (USERNAME,)).fetchone()
        correct, total = (row[0] or 0), (row[1] or 0)
        accuracy = round(correct / total, 4) if total else 0.0
        plan = conn.execute("SELECT total_days, plan_json FROM study_plans WHERE user_id=? AND status='active'",
                            (USERNAME,)).fetchone()
        plan_days = len(json.loads(plan[1])["days"]) if plan else 0
        wrow = conn.execute(
            "SELECT MIN(total_score), MAX(total_score), COUNT(*) FROM writing_grade_results WHERE user_id=?",
            (USERNAME,)).fetchone()
        vocab_new = conn.execute(
            "SELECT COUNT(*) FROM vocabulary_daily_cards WHERE user_id=? AND card_type='new'", (USERNAME,)).fetchone()[0]
        vocab_review = conn.execute(
            "SELECT COUNT(*) FROM vocabulary_daily_cards WHERE user_id=? AND card_type='review'", (USERNAME,)).fetchone()[0]
        vocab_days = conn.execute(
            "SELECT COUNT(DISTINCT study_date) FROM vocabulary_daily_cards WHERE user_id=?", (USERNAME,)).fetchone()[0]
        balance = conn.execute("SELECT balance FROM credit_accounts WHERE user_id=?", (USERNAME,)).fetchone()
        ledger = conn.execute("SELECT COUNT(*) FROM credit_ledger WHERE user_id=?", (USERNAME,)).fetchone()[0]
        mindmaps = conn.execute("SELECT COUNT(*) FROM mindmaps WHERE user_id=?", (USERNAME,)).fetchone()[0]

        problems = []
        if papers != 31 or submitted != 31:
            problems.append(f"papers={papers} submitted={submitted} (want 31/31)")
        if plan_days != 30:
            problems.append(f"plan_days={plan_days} (want 30)")
        if not (0.80 <= accuracy <= 0.95):
            problems.append(f"accuracy={accuracy} (want ~0.90)")
        if not wrow[2]:
            problems.append("no writing grade on the mock")
        if wrow[2] and (wrow[0] is None or wrow[0] < 0 or wrow[1] > 20):
            problems.append(f"writing score out of 0-20 range: {wrow[:2]}")
        if vocab_new != NEW_PER_DAY * 30 or vocab_days != 30:
            problems.append(f"vocab_new={vocab_new} days={vocab_days} (want {NEW_PER_DAY*30}/30)")
        if problems:
            raise RuntimeError("verify failed: " + "; ".join(problems))

        return {"papers": papers, "submitted": submitted, "objective_accuracy": accuracy,
                "plan_days": plan_days, "writing": {"count": wrow[2], "min": wrow[0], "max": wrow[1]},
                "vocab_new": vocab_new, "vocab_review": vocab_review, "vocab_days": vocab_days,
                "balance": balance[0] if balance else None, "ledger_rows": ledger, "mindmaps": mindmaps}
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the `zecheng` learner via the real pipeline (no-LLM branch + real writing grade). Any existing zecheng is deleted and recreated with a 2026-08-01 join date.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    result = verify(args.db) if args.verify else seed(args.db)
    print(json.dumps(result, ensure_ascii=False))
    if not args.verify:
        print(f"database: {args.db}\naccount: {USERNAME} / {PASSWORD}")


if __name__ == "__main__":
    main()
