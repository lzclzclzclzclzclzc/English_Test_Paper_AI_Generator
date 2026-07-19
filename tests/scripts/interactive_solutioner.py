"""Interactive Solutioner tester.

Run:
    PYTHONIOENCODING=utf-8 python tests/scripts/interactive_solutioner.py

Two ways to feed a question:
  1. 从题库随机抽一道原题（走缓存/写回逻辑，revision_mode=original）
  2. 手动输入一道单选题（无溯源，纯生成）

Type 'exit' / 'q' or Ctrl+C to quit.
"""
from __future__ import annotations

import json
import sqlite3
import sys
import time
from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from ai_engine.solutioner import generate_solution
from shared.config import get_config
from shared.schemas import Option, Question, RevisedQuestion


def _load_random_original(question_type: str | None = None) -> tuple[RevisedQuestion, str]:
    """Pull one random question from the bank. Returns (RevisedQuestion, source_id)."""
    cfg = get_config()
    conn = sqlite3.connect(str(cfg.db_path))
    conn.row_factory = sqlite3.Row
    try:
        sql = "SELECT * FROM questions"
        params: list = []
        if question_type:
            sql += " WHERE question_type = ?"
            params.append(question_type)
        sql += " ORDER BY RANDOM() LIMIT 1"
        row = conn.execute(sql, params).fetchone()
        if row is None:
            raise RuntimeError("题库为空或没有匹配的题型")

        kp_ids = [
            r["knowledge_point_id"]
            for r in conn.execute(
                "SELECT knowledge_point_id FROM question_knowledge_points WHERE question_id = ?",
                (row["id"],),
            )
        ]
    finally:
        conn.close()

    options = None
    if row["options_json"]:
        options = [Option(**o) for o in json.loads(row["options_json"])]

    rq = RevisedQuestion(
        question_type=row["question_type"],
        knowledge_point_ids=kp_ids,
        stem=row["stem"],
        options=options,
        hint=row["hint"],
        original_sentence=row["original_sentence"],
        instruction=row["instruction"],
        template=row["template"],
        answer=json.loads(row["answer_json"]),
    )
    return rq, row["id"]


def _prompt_manual_sc() -> RevisedQuestion:
    """Ask the user to type a single_choice question by hand."""
    stem = input("  题干: ").strip()
    print("  输入 4 个选项:")
    options = []
    for label in ("A", "B", "C", "D"):
        text = input(f"    {label}. ").strip()
        options.append(Option(label=label, text=text))
    answer = input("  正确答案 (A/B/C/D): ").strip().upper()
    kp = input("  知识点 id（可留空）: ").strip()
    return RevisedQuestion(
        question_type="single_choice",
        knowledge_point_ids=[kp] if kp else [],
        stem=stem,
        options=options,
        answer=answer,
    )


def _show_question(q: RevisedQuestion, source_id: str | None) -> None:
    print("\n  ── 题目 ──")
    print(f"  题型: {q.question_type}  KP: {q.knowledge_point_ids or '（无）'}"
          f"{'  溯源: ' + source_id if source_id else '  （无溯源）'}")
    if q.stem:
        print(f"  题干: {q.stem}")
    if q.original_sentence:
        print(f"  原句: {q.original_sentence}")
    if q.instruction:
        print(f"  要求: {q.instruction}")
    if q.template:
        print(f"  模板: {q.template}")
    if q.hint:
        print(f"  提示词: {q.hint}")
    if q.options:
        for o in q.options:
            print(f"    {o.label}. {o.text}")
    print(f"  答案: {q.answer}")


def main() -> None:
    print("=" * 60)
    print("  Interactive Solutioner — 单题解析生成")
    print("=" * 60)
    print("  选择输入方式：")
    print("    1  从题库随机抽一道原题（走缓存/写回，revision_mode=original）")
    print("    1c 同上但只抽单选 / 1w 只抽词性转换 / 1s 只抽改写句子")
    print("    2  手动输入一道单选题（无溯源，纯生成）")
    print("  输入 'exit' / 'q' 或 Ctrl+C 退出")
    print("=" * 60)

    type_map = {"1c": "single_choice", "1w": "word_form", "1s": "sentence_rewriting"}

    while True:
        try:
            print()
            choice = input("选择 (1 / 1c / 1w / 1s / 2)> ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print("\n\n退出。")
            break

        if choice in ("exit", "quit", "q"):
            print("退出。")
            break

        try:
            if choice == "1":
                q, source_id = _load_random_original()
                revision_mode = "original"
            elif choice in type_map:
                q, source_id = _load_random_original(type_map[choice])
                revision_mode = "original"
            elif choice == "2":
                q = _prompt_manual_sc()
                source_id = None
                revision_mode = None
            else:
                print("  无效选择")
                continue

            _show_question(q, source_id)

            print("\n  ⏳ 生成解析中 ...")
            t0 = time.time()
            solution = generate_solution(
                q, source_question_id=source_id, revision_mode=revision_mode
            )
            elapsed = time.time() - t0

            # cache hit is near-instant; a real LLM call takes seconds
            cache_note = "（疑似缓存命中）" if elapsed < 0.5 and source_id else ""
            print(f"  ✅ 完成（{elapsed:.2f}s）{cache_note}")
            print("\n" + "─" * 60)
            print(solution)
            print("─" * 60)

        except Exception as e:
            print(f"  ❌ 失败: {e}")


if __name__ == "__main__":
    main()
