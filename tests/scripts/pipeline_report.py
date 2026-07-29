"""Full pipeline smoke-test: run 10 representative prompts through
generate_paper() and write a Markdown report.

Usage
-----
    PYTHONIOENCODING=utf-8 python tests/scripts/pipeline_report.py

Output: tests/scripts/pipeline_report_<YYYYMMDD_HHMMSS>.md
"""
from __future__ import annotations

import sys
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Make sure project root is on sys.path when run directly.
_PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from ai_engine.pipeline import generate_paper
from shared.schemas import Paper, PaperItem, RevisedQuestion


# ---------------------------------------------------------------------------
# 10 test cases — each covers a distinct retrieval / revision path
# ---------------------------------------------------------------------------
TEST_CASES: list[dict[str, Any]] = [
    {
        "id": 1,
        "label": "KP过滤 · light",
        "desc": "指定知识点 + 单选，走 SQL 随机路径，默认 light 档改写",
        "query": "来10道现在完成时的单选题",
        "kwargs": {},
    },
    {
        "id": 2,
        "label": "题型分布",
        "desc": "明确指定 5 道单选 + 5 道词性转换，检验 type_distribution 分桶",
        "query": "帮我出5道单选题和5道词性转换题",
        "kwargs": {},
    },
    {
        "id": 3,
        "label": "original档 · 真题",
        "desc": "用户要原题，Parser 应推断 revision_intensity=original，LLM 不改题",
        "query": "来10道中考真题单选，不要改动",
        "kwargs": {},
    },
    {
        "id": 4,
        "label": "语义向量路径",
        "desc": "含具体情境主题 '环保'，free_text 非空，走 Chroma 向量检索",
        "query": "来5道关于环保的单选题",
        "kwargs": {},
    },
    {
        "id": 5,
        "label": "fresh档 · 全新出题",
        "desc": "明确要求 '全新'，Parser 应推断 revision_intensity=fresh",
        "query": "帮我全新出8道动词时态单选题，别用现成的",
        "kwargs": {},
    },
    {
        "id": 6,
        "label": "fresh档 · 情境触发",
        "desc": "含校园场景情境描述，触发 fresh 档 + 向量路径",
        "query": "结合校园生活场景出6道单选练习题",
        "kwargs": {},
    },
    {
        "id": 7,
        "label": "无限制 · 随机",
        "desc": "无任何过滤条件，全库随机取题，检验兜底路径",
        "query": "随便出10道英语练习题",
        "kwargs": {},
    },
    {
        "id": 8,
        "label": "多KP过滤",
        "desc": "同时指定介词 + 冠词两个 KP，检验 OR 过滤合并",
        "query": "来8道介词和冠词的混合单选题",
        "kwargs": {},
    },
    {
        "id": 9,
        "label": "改写句子题",
        "desc": "只要改写句子题型，检验非单选题的 light 档改写",
        "query": "来6道改写句子的练习题，巩固一下",
        "kwargs": {},
    },
    {
        "id": 10,
        "label": "remediation模式",
        "desc": "remediation 模式传入错题列表，检验 Parser 上下文注入",
        "query": "针对我的错题再练几道单选",
        "kwargs": {
            "mode": "remediation",
            "wrong_items": [
                {
                    "question_type": "single_choice",
                    "knowledge_point_ids": ["kp_sc_verbs"],
                },
                {
                    "question_type": "single_choice",
                    "knowledge_point_ids": ["kp_sc_prepositions"],
                },
            ],
        },
    },
]


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------
@dataclass
class TestResult:
    case: dict
    elapsed: float = 0.0
    paper: Paper | None = None
    error: str = ""
    status: str = "ok"  # "ok" | "error"


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

def _run_cases(cases: list[dict]) -> list[TestResult]:
    results: list[TestResult] = []
    for case in cases:
        print(f"  [{case['id']:02d}/10] {case['label']} ... ", end="", flush=True)
        t0 = time.time()

        # remediation mode needs WrongItemRef objects, not raw dicts
        kwargs = dict(case["kwargs"])
        if "wrong_items" in kwargs:
            from shared.schemas import WrongItemRef
            kwargs["wrong_items"] = [
                WrongItemRef(**w) for w in kwargs["wrong_items"]
            ]

        try:
            paper = generate_paper(case["query"], **kwargs)
            elapsed = time.time() - t0
            print(f"✓ ({elapsed:.1f}s)")
            results.append(TestResult(case=case, elapsed=elapsed, paper=paper, status="ok"))
        except Exception as e:
            elapsed = time.time() - t0
            print(f"✗ ({elapsed:.1f}s) {e}")
            results.append(TestResult(
                case=case, elapsed=elapsed, status="error",
                error=traceback.format_exc(),
            ))
    return results


# ---------------------------------------------------------------------------
# Markdown rendering helpers
# ---------------------------------------------------------------------------

def _fmt_answer(answer) -> str:
    if isinstance(answer, str):
        return answer
    if isinstance(answer, list):
        parts = []
        for group in answer:
            parts.append(" / ".join(
                f"{k}: {' | '.join(v)}" for k, v in group.items()
            ))
        return "；".join(parts)
    return str(answer)


def _render_question(item: PaperItem, idx: int) -> str:
    q = item.question
    lines: list[str] = []
    lines.append(f"**{idx}.** `{q.question_type}` | KP: `{'`, `'.join(q.knowledge_point_ids)}`  "
                 f"← 源题 `{item.source_question_id}` (档位: `{item.revision_mode}`)")

    if q.stem:
        lines.append(f"> {q.stem}")
    if q.hint:
        lines.append(f"> 提示: _{q.hint}_")
    if q.original_sentence:
        lines.append(f"> 原句: {q.original_sentence}")
    if q.instruction:
        lines.append(f"> 指令: {q.instruction}")
    if q.template:
        lines.append(f"> 模板: `{q.template}`")

    if q.options:
        for opt in q.options:
            lines.append(f"> - **{opt.label}.** {opt.text}")

    lines.append(f"> **答案:** {_fmt_answer(q.answer)}")
    return "\n".join(lines)


def _render_result(r: TestResult) -> str:
    c = r.case
    lines: list[str] = []
    lines.append(f"## Case {c['id']:02d} — {c['label']}")
    lines.append(f"")
    lines.append(f"| 字段 | 值 |")
    lines.append(f"|------|-----|")
    lines.append(f"| Prompt | `{c['query']}` |")
    lines.append(f"| 描述 | {c['desc']} |")
    lines.append(f"| 状态 | {'✅ 通过' if r.status == 'ok' else '❌ 失败'} |")
    lines.append(f"| 耗时 | {r.elapsed:.2f}s |")

    if r.status == "error":
        lines.append(f"")
        lines.append(f"### 错误详情")
        lines.append(f"```")
        lines.append(r.error.strip())
        lines.append(f"```")
        return "\n".join(lines)

    paper = r.paper
    req = paper.request

    lines.append(f"")
    lines.append(f"### Parser 解析结果")
    lines.append(f"")
    lines.append(f"| 字段 | 值 |")
    lines.append(f"|------|-----|")
    lines.append(f"| mode | `{req.mode}` |")
    lines.append(f"| total_questions | {req.total_questions} |")
    lines.append(f"| question_types | `{req.question_types or '(不限)'}` |")
    lines.append(f"| knowledge_points | `{req.knowledge_points or '(不限)'}` |")
    lines.append(f"| type_distribution | `{req.type_distribution or '{}'}` |")
    lines.append(f"| revision_intensity | `{req.revision_intensity}` |")
    lines.append(f"| free_text | `{req.free_text!r}` |")

    lines.append(f"")
    lines.append(f"### 试卷 — {paper.title}")
    lines.append(f"")
    lines.append(f"共 **{len(paper.items)}** 道题  |  "
                 f"LLM 调用: **{paper.metadata.get('llm_calls', '?')}** 次")

    if paper.metadata.get("retrieval_warnings"):
        lines.append(f"")
        lines.append(f"> ⚠️ 检索警告: " + "；".join(paper.metadata["retrieval_warnings"]))

    if paper.metadata.get("shortfall"):
        lines.append(f"> ⚠️ 缺口: {paper.metadata['shortfall']}")

    lines.append(f"")
    for item in paper.items:
        lines.append(_render_question(item, item.index))
        lines.append(f"")

    return "\n".join(lines)


def _render_report(results: list[TestResult]) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    ok = sum(1 for r in results if r.status == "ok")
    total_time = sum(r.elapsed for r in results)

    lines: list[str] = []
    lines.append(f"# Pipeline 完整测试报告")
    lines.append(f"")
    lines.append(f"**生成时间**: {now}  ")
    lines.append(f"**通过 / 总计**: {ok} / {len(results)}  ")
    lines.append(f"**总耗时**: {total_time:.1f}s  ")
    lines.append(f"")
    lines.append(f"## 汇总")
    lines.append(f"")
    lines.append(f"| # | 标签 | Prompt | 状态 | 耗时 | 题数 | 改题档位 |")
    lines.append(f"|---|------|--------|------|------|------|----------|")

    for r in results:
        status = "✅" if r.status == "ok" else "❌"
        count = len(r.paper.items) if r.paper else "-"
        intensity = r.paper.request.revision_intensity if r.paper else "-"
        lines.append(
            f"| {r.case['id']} | {r.case['label']} | {r.case['query']} "
            f"| {status} | {r.elapsed:.1f}s | {count} | `{intensity}` |"
        )

    lines.append(f"")
    lines.append(f"---")
    lines.append(f"")

    for r in results:
        lines.append(_render_result(r))
        lines.append(f"")
        lines.append(f"---")
        lines.append(f"")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 60)
    print("  Pipeline 完整测试 (10 prompts)")
    print("=" * 60)

    results = _run_cases(TEST_CASES)

    report_md = _render_report(results)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = Path(__file__).parent / f"pipeline_report_{ts}.md"
    out_path.write_text(report_md, encoding="utf-8")

    ok = sum(1 for r in results if r.status == "ok")
    print(f"\n{'=' * 60}")
    print(f"  完成: {ok}/{len(results)} 通过")
    print(f"  报告: {out_path}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
