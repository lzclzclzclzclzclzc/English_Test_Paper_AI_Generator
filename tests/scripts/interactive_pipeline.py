"""Interactive full-pipeline tester.

Run:
    PYTHONIOENCODING=utf-8 python tests/scripts/interactive_pipeline.py

Input a natural-language prompt, watch the pipeline run, see the paper.
Type 'exit' / 'q' or press Ctrl+C to quit.
"""
from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from ai_engine.errors import ParserError
from shared.schemas import PaperItem


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def _fmt_answer(answer) -> str:
    if isinstance(answer, str):
        return answer
    if isinstance(answer, list):
        parts = []
        for group in answer:
            parts.append("  ".join(f"{k}: {' | '.join(v)}" for k, v in group.items()))
        return "；".join(parts)
    return str(answer)


def _print_item(item: PaperItem) -> None:
    q = item.question
    print(f"\n  [{item.index}] {q.question_type}  "
          f"KP: {', '.join(q.knowledge_point_ids)}  "
          f"← {item.source_question_id} ({item.revision_mode})")

    if q.stem:
        print(f"      题干: {q.stem}")
    if q.hint:
        print(f"      提示: {q.hint}")
    if q.original_sentence:
        print(f"      原句: {q.original_sentence}")
    if q.instruction:
        print(f"      指令: {q.instruction}")
    if q.template:
        print(f"      模板: {q.template}")

    if q.options:
        for opt in q.options:
            print(f"        {opt.label}. {opt.text}")

    print(f"      答案: {_fmt_answer(q.answer)}")


def _print_paper(paper) -> None:
    req = paper.request
    print()
    print("─" * 60)
    print(f"  📄 {paper.title}")
    print("─" * 60)
    print(f"  mode={req.mode}  intensity={req.revision_intensity}  "
          f"题数={len(paper.items)}  LLM调用={paper.metadata.get('llm_calls', '?')}次")
    if req.knowledge_points:
        print(f"  KP过滤: {req.knowledge_points}")
    if req.question_types:
        print(f"  题型: {req.question_types}")
    if req.type_distribution:
        print(f"  分布: {req.type_distribution}")
    if req.free_text:
        print(f"  语义主题: {req.free_text!r}")
    if paper.metadata.get("retrieval_warnings"):
        for w in paper.metadata["retrieval_warnings"]:
            print(f"  ⚠️  {w}")

    for item in paper.items:
        _print_item(item)

    print()
    print("─" * 60)


# ---------------------------------------------------------------------------
# Main REPL
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 60)
    print("  Interactive Pipeline — 完整端到端测试")
    print("=" * 60)
    print("  输入自然语言 prompt，回车运行整个 pipeline")
    print("  支持前缀选项（可省略）：")
    print("    --mode remediation   切换到错题补练模式")
    print("    --mode review        切换到历史复习模式（需要 --user user_id）")
    print("  输入 'exit' / 'q' 或按 Ctrl+C 退出")
    print("=" * 60)

    while True:
        try:
            print()
            raw = input("prompt> ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\n退出。")
            break

        if not raw:
            continue
        if raw.lower() in ("exit", "quit", "q"):
            print("退出。")
            break

        # Simple option parsing: --key value tokens stripped from front
        tokens = raw.split()
        kwargs: dict = {}
        query_tokens: list[str] = []
        i = 0
        while i < len(tokens):
            if tokens[i] == "--mode" and i + 1 < len(tokens):
                kwargs["mode"] = tokens[i + 1]
                i += 2
            elif tokens[i] == "--user" and i + 1 < len(tokens):
                kwargs["user_id"] = tokens[i + 1]
                i += 2
            elif tokens[i] == "--days" and i + 1 < len(tokens):
                try:
                    kwargs["review_window_days"] = int(tokens[i + 1])
                except ValueError:
                    pass
                i += 2
            else:
                query_tokens.append(tokens[i])
                i += 1

        query = " ".join(query_tokens)
        if not query:
            print("  (空 prompt，跳过)")
            continue

        mode = kwargs.get("mode", "fresh")
        if mode not in ("fresh", "remediation", "review"):
            print(f"  ⚠️  未知 mode '{mode}'，使用 fresh")
            kwargs["mode"] = "fresh"

        print(f"\n  ⏳ 启动 pipeline（mode={mode}）...")
        import time
        t_start = time.time()
        try:
            # --- Stage 1: Parser ---
            print(f"  [1/3] Parser  正在解析 prompt ...", end="", flush=True)
            t0 = time.time()
            from ai_engine import parser as _parser
            import ai_engine.retriever as _retriever
            import ai_engine.reviser as _reviser
            from shared.schemas import WrongItemRef

            # build parser kwargs
            parse_kwargs: dict = {"mode": kwargs.get("mode", "fresh")}
            if "wrong_items" in kwargs:
                parse_kwargs["wrong_items"] = kwargs["wrong_items"]
            if "user_id" in kwargs:
                parse_kwargs["user_id"] = kwargs["user_id"]
            if "review_window_days" in kwargs:
                parse_kwargs["review_window_days"] = kwargs["review_window_days"]

            # review mode: run build_profile first
            mastery = None
            if kwargs.get("mode") == "review":
                from ai_engine.pipeline import build_profile
                mastery = build_profile(
                    kwargs["user_id"],
                    kwargs.get("review_window_days"),
                )
                parse_kwargs["mastery"] = mastery

            req = _parser.parse(query, **parse_kwargs)
            t1 = time.time()
            print(f" ✓  {t1 - t0:.2f}s")
            print(f"      → mode={req.mode}  intensity={req.revision_intensity}  "
                  f"total={req.total_questions}  "
                  f"KP={req.knowledge_points or '不限'}  "
                  f"types={req.question_types or '不限'}  "
                  f"free_text={req.free_text!r}")

            # --- Stage 2: Retriever ---
            print(f"  [2/3] Retriever  正在检索题目 ...", end="", flush=True)
            t0 = time.time()
            retrieval = _retriever.retrieve(req)
            t2 = time.time()
            shortfall_info = f"  缺口={retrieval.shortfall}" if retrieval.shortfall else ""
            print(f" ✓  {t2 - t0:.2f}s  → 候选 {len(retrieval.items)} 题{shortfall_info}")

            # --- Stage 3: Reviser ---
            n_llm = len(retrieval.items) if req.revision_intensity != "original" else 0
            print(f"  [3/3] Reviser   正在改写题目（{req.revision_intensity}档"
                  f"{'，预计 ' + str(n_llm) + ' 次 LLM 调用' if n_llm else '，无 LLM 调用'}）...",
                  end="", flush=True)
            t0 = time.time()
            paper = _reviser.build_paper(req, retrieval)
            t3 = time.time()
            print(f" ✓  {t3 - t0:.2f}s")

            elapsed = time.time() - t_start
            _print_paper(paper)
            print(f"  ⏱  总耗时（prompt → 题目全部显示）: {elapsed:.2f}s"
                  f"  （Parser {t1-t_start:.2f}s / Retriever {t2-t1:.2f}s / Reviser {t3-t2:.2f}s）")
        except Exception as e:
            elapsed = time.time() - t_start
            print(f"\n  ❌ 失败（{elapsed:.1f}s）: {e}")


if __name__ == "__main__":
    main()
