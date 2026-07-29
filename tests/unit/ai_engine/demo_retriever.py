"""Generate a Markdown report of the Retriever's behaviour across sample requests.

    python tests/unit/ai_engine/demo_retriever.py            # writes report next to this file
    python tests/unit/ai_engine/demo_retriever.py --out x.md # custom path

For each sample request it records the input GenerateRequest and the questions
retrieved (with similarity scores on the vector path). Handy for reports /
demos / PR attachments — the unit tests only assert, this shows.

Uses the real bank + vectors + Qwen model; the semantic samples load the model
so the first run takes a bit.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running as a plain script (python tests/.../demo_retriever.py): add the
# project root to sys.path so `ai_engine` / `shared` import cleanly.
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from ai_engine.retriever import Retriever            # noqa: E402
from shared.schemas import GenerateRequest           # noqa: E402

# Report is written next to this script by default.
DEFAULT_OUT = Path(__file__).resolve().parent / "retriever_report.md"

# Ten samples, each tagged with the natural-language intent it simulates and
# the retrieval path it exercises.
SAMPLES: list[dict] = [
    {
        "title": "5 单选 + 5 改写",
        "user_says": "5 道单选 + 5 道改写",
        "path": "配额分桶 · SQL 随机",
        "req": GenerateRequest(
            total_questions=10,
            type_distribution={"single_choice": 5, "sentence_rewriting": 5},
        ),
    },
    {
        "title": "8 道时态单选",
        "user_says": "8 道时态的单选题",
        "path": "KP 硬过滤 · SQL 随机",
        "req": GenerateRequest(
            total_questions=8,
            knowledge_points=["kp_sc_verbs"],
            question_types=["single_choice"],
        ),
    },
    {
        "title": "关于环保的单选",
        "user_says": "来几道关于环保的单选",
        "path": "向量语义检索 · RAG",
        "req": GenerateRequest(
            total_questions=5,
            question_types=["single_choice"],
            free_text="关于环保 环境保护 污染",
        ),
    },
    {
        "title": "冷门 KP 超量请求",
        "user_says": "多出点其他类的题（映射到冷门 KP）",
        "path": "shortfall 兜底（库仅 2 道，要 50 道）",
        "req": GenerateRequest(
            total_questions=50,
            knowledge_points=["kp_sc_misc"],
            question_types=["single_choice"],
        ),
    },
    {
        "title": "随便 5 道",
        "user_says": "随便来 5 道",
        "path": "无过滤 · 全库随机",
        "req": GenerateRequest(total_questions=5),
    },
    {
        "title": "6 道名词复数（词性转换）",
        "user_says": "来 6 道名词变复数的词性转换",
        "path": "KP 硬过滤 · SQL 随机（词性转换题型）",
        "req": GenerateRequest(
            total_questions=6,
            knowledge_points=["kp_wf_noun_plural"],
            question_types=["word_form"],
        ),
    },
    {
        "title": "5 道被动语态改写",
        "user_says": "出 5 道被动语态的改写句子",
        "path": "KP 硬过滤 · SQL 随机（改写题型）",
        "req": GenerateRequest(
            total_questions=5,
            knowledge_points=["kp_sr_passive_voice"],
            question_types=["sentence_rewriting"],
        ),
    },
    {
        "title": "三题型混合配额",
        "user_says": "4 道单选、3 道词性转换、3 道改写",
        "path": "三桶配额分配 · SQL 随机",
        "req": GenerateRequest(
            total_questions=10,
            type_distribution={
                "single_choice": 4,
                "word_form": 3,
                "sentence_rewriting": 3,
            },
        ),
    },
    {
        "title": "关于科技的单选",
        "user_says": "来几道关于手机、网络、科技的单选",
        "path": "向量语义检索 · RAG（另一主题，验证不止环保有效）",
        "req": GenerateRequest(
            total_questions=5,
            question_types=["single_choice"],
            free_text="手机 网络 科技 technology internet",
        ),
    },
    {
        "title": "介词 + 旅游主题",
        "user_says": "来 5 道跟旅游有关的介词单选",
        "path": "KP 硬过滤 + 向量语义（两者同时生效）",
        "req": GenerateRequest(
            total_questions=5,
            knowledge_points=["kp_sc_prepositions"],
            question_types=["single_choice"],
            free_text="关于旅游 出行 travel trip",
        ),
    },
]


def _content_preview(q) -> str:
    """One-line, markdown-safe preview of a question's content."""
    text = q.stem or q.original_sentence or ""
    text = text[:90].replace("\n", " ").replace("|", "\\|")
    return text


def _req_summary(req: GenerateRequest) -> str:
    parts = [
        f"`total_questions={req.total_questions}`",
        f"`question_types={req.question_types or '[]'}`",
        f"`knowledge_points={req.knowledge_points or '[]'}`",
        f"`type_distribution={req.type_distribution or '{}'}`",
        f"`free_text={req.free_text!r}`",
    ]
    return "<br>".join(parts)


def build_report() -> str:
    retriever = Retriever(seed=42)
    lines: list[str] = []

    lines.append("# Retriever 检索结果报告")
    lines.append("")
    lines.append("> 由 `tests/unit/ai_engine/demo_retriever.py` 生成。"
                 "使用真实题库（`data/questions.db`）+ 向量库（`data/chroma/`）"
                 "+ Qwen3-Embedding-4B。种子固定为 42，SQL 随机路径可复现。")
    lines.append("")
    lines.append(f"共 {len(SAMPLES)} 个样例，覆盖 Retriever 的全部路径：属性配额分桶、"
                 "KP 硬过滤（三种题型）、向量语义检索（RAG，多主题）、KP+语义组合、"
                 "shortfall 兜底、全库随机。")
    lines.append("")

    for i, s in enumerate(SAMPLES, 1):
        req: GenerateRequest = s["req"]
        res = retriever.retrieve(req)

        lines.append(f"## 样例 {i}：{s['title']}")
        lines.append("")
        lines.append(f"- **用户诉求**：「{s['user_says']}」")
        lines.append(f"- **检索路径**：{s['path']}")
        lines.append(f"- **GenerateRequest**：{_req_summary(req)}")
        got = len(res.items)
        short = f"，**shortfall = {res.shortfall}**" if res.shortfall else ""
        lines.append(f"- **结果**：取到 {got} 道{short}")
        lines.append("")

        # Result table
        lines.append("| # | id | 题型 | 相似度 | 内容预览 |")
        lines.append("|---|----|------|-------|---------|")
        for idx, it in enumerate(res.items, 1):
            q = it.question
            score = f"{it.score:.3f}" if it.score > 0 else "— (随机)"
            lines.append(
                f"| {idx} | {q.id} | {q.question_type} | {score} | {_content_preview(q)} |"
            )
        lines.append("")

        if res.warnings:
            for w in res.warnings:
                lines.append(f"> ⚠ {w}")
            lines.append("")

    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT,
                    help="Output markdown path (default: data/retriever_report.md)")
    args = ap.parse_args()

    report = build_report()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(report, encoding="utf-8")
    print(f"[OK] wrote {args.out}")


if __name__ == "__main__":
    main()
