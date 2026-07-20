#!/usr/bin/env python3
"""Interactive Reviser module tester.

Run to enter a REPL loop for testing the Reviser module.
Input parameters and see the paper generation results.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from typing import Literal

sys.path.insert(0, str(Path(__file__).parent.parent))

from ai_engine.reviser import build_paper
from shared.config import get_config
from shared.schemas import (
    Answer,
    GenerateRequest,
    Option,
    Question,
    QuestionType,
    RetrievedItem,
    RetrievalResult,
    RevisionMode,
)


def _load_sample_questions(
    question_type: QuestionType | None = None,
    limit: int = 5,
) -> list[Question]:
    """Load sample questions from database."""
    cfg = get_config()
    conn = sqlite3.connect(str(cfg.db_path))
    conn.row_factory = sqlite3.Row

    try:
        query = "SELECT * FROM questions"
        params = []

        if question_type:
            query += " WHERE question_type = ?"
            params.append(question_type)

        query += " ORDER BY RANDOM() LIMIT ?"
        params.append(limit)

        cursor = conn.execute(query, params)
        questions = []

        for row in cursor.fetchall():
            options = json.loads(row["options_json"]) if row["options_json"] else None
            if options:
                options = [Option(**opt) for opt in options]

            answer = json.loads(row["answer_json"]) if row["answer_json"] else row["answer"]

            kp_ids = []
            kp_cursor = conn.execute(
                "SELECT knowledge_point_id FROM question_knowledge_points WHERE question_id = ?",
                (row["id"],)
            )
            for kp_row in kp_cursor.fetchall():
                kp_ids.append(kp_row["knowledge_point_id"])

            questions.append(Question(
                id=row["id"],
                book=row["book"],
                question_type=row["question_type"],
                chapter_l1=row["chapter_l1"],
                chapter_l2=row["chapter_l2"],
                number=row["number"],
                stem=row["stem"],
                options=options,
                hint=row["hint"],
                original_sentence=row["original_sentence"],
                instruction=row["instruction"],
                template=row["template"],
                answer=answer,
                solution=row["solution"],
                knowledge_point_ids=kp_ids,
                source_md=row["source_md"],
                source_line=row["source_line"],
                created_at=row["created_at"],
                version=row["version"],
            ))

        return questions
    finally:
        conn.close()


def main() -> None:
    print("=" * 60)
    print("  Interactive Reviser Tester")
    print("=" * 60)
    print("输入参数测试题目修订，按 Ctrl+C 或输入 'exit' 退出")
    print("=" * 60)

    while True:
        try:
            print()

            user_query = input("输入用户查询 (用于语义提示): ").strip()
            if user_query.lower() in ("exit", "quit", "q"):
                print("退出...")
                break

            question_type_input = input("题目类型 (single_choice/word_form/sentence_rewriting/all): ").strip()
            if question_type_input.lower() in ("exit", "quit", "q"):
                print("退出...")
                break

            question_type: QuestionType | None = None
            if question_type_input and question_type_input != "all":
                if question_type_input in ("single_choice", "word_form", "sentence_rewriting"):
                    question_type = question_type_input
                else:
                    print("无效的题目类型，使用 all")

            try:
                count = int(input("题目数量 (默认5): ").strip() or "5")
            except ValueError:
                count = 5

            mode_input = input("修订模式 (fresh/light/original，默认light): ").strip()
            if mode_input.lower() in ("exit", "quit", "q"):
                print("退出...")
                break

            revision_mode: RevisionMode = mode_input if mode_input else "light"
            if revision_mode not in ("fresh", "light", "original"):
                print("无效的修订模式，使用 light")
                revision_mode = "light"

            print("\n正在加载题目并修订...")

            questions = _load_sample_questions(question_type, count)
            if not questions:
                print("没有找到题目")
                continue

            retrieval_result = RetrievalResult(
                items=[
                    RetrievedItem(question=q, score=0.8)
                    for q in questions
                ]
            )

            request = GenerateRequest(
                total_questions=count,
                question_types=[q.question_type for q in questions],
                revision_intensity=revision_mode,
                free_text=user_query,
            )

            paper = build_paper(request, retrieval_result)

            print("\n" + "=" * 60)
            print(f"试卷标题: {paper.title}")
            print(f"题目数量: {len(paper.items)}")
            print(f"修订模式: {revision_mode}")
            print("=" * 60)

            for item in paper.items:
                print(f"\n--- 题目 {item.index} ---")
                print(f"类型: {item.question.question_type}")
                print(f"知识点: {', '.join(item.question.knowledge_point_ids)}")
                print(f"来源: {item.source_question_id}")
                print(f"修订模式: {item.revision_mode}")

                if item.question.stem:
                    print(f"\n题干: {item.question.stem}")

                if item.question.options:
                    print("\n选项:")
                    for opt in item.question.options:
                        print(f"  {opt.label}. {opt.text}")

                if item.question.hint:
                    print(f"\n提示: {item.question.hint}")

                if item.question.original_sentence:
                    print(f"\n原句: {item.question.original_sentence}")

                if item.question.instruction:
                    print(f"\n指令: {item.question.instruction}")

                if item.question.template:
                    print(f"\n模板: {item.question.template}")

                print(f"\n答案: {item.question.answer}")

                if item.question.solution:
                    print(f"\n解析: {item.question.solution}")

        except KeyboardInterrupt:
            print("\n\n退出...")
            break
        except Exception as e:
            print(f"\n错误: {e}")


if __name__ == "__main__":
    main()
