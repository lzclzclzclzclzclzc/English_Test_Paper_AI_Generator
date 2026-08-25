"""AI Engine top-level orchestration (Spec B §2).

Pure pipeline, no feedback loops, no agent framework:

    generate_paper:  (review → Analyzer) → Parser → Retriever → Reviser → Paper
    revise_paper:    Parser(instruction) → (Retriever/Reviser) → Paper
    generate_solution: Solutioner (standalone)
    build_profile:   Analyzer (standalone)

Every cross-module call speaks ONLY in `shared.schemas` types — this file
doesn't know or care how Parser/Reviser/Analyzer are implemented internally,
only that they honour the contract:

    parser.parse(user_query, *, mode, wrong_items, mastery) -> GenerateRequest
    retriever.retrieve(req)                                  -> RetrievalResult
    reviser.build_paper(req, retrieval)                      -> Paper
    solutioner.generate_solution(q, *, ...)                  -> str
    analyzer.build_profile(user_id, window_days)             -> MasteryProfile

The sibling modules are imported lazily inside each function. That keeps
`import ai_engine.pipeline` cheap and, crucially, lets this module load even
while Parser/Reviser/Analyzer are still being written on another branch —
only a call that actually reaches an unfinished module fails, and it fails
with a clear ImportError rather than breaking the whole package.

Statelessness (Spec B §1.2): every call returns fresh objects; the engine
writes no SQL. Persistence is the backend's job (Spec C).
"""
from __future__ import annotations

from typing import Callable

from ai_engine.errors import ParserError
from shared.schemas import (
    GenerateMode,
    GenerateRequest,
    MasteryProfile,
    Paper,
    QUESTION_TYPE_LABELS,
    RevisedQuestion,
    RevisionMode,
    WrongItemRef,
)


# ─────────────────────────────────────────────────────────────────────────────
# generate_paper — the main pipeline
# ─────────────────────────────────────────────────────────────────────────────
def generate_paper(
    user_query: str,
    mode: GenerateMode = "fresh",
    *,
    wrong_items: list[WrongItemRef] | None = None,
    user_id: str | None = None,
    review_window_days: int | None = None,
    on_request: Callable[[GenerateRequest], None] | None = None,
) -> Paper:
    """Natural-language request → a full Paper.

    `on_request` (optional) is invoked with the parsed GenerateRequest right
    after the Parser and before any retrieval / LLM revision work. The backend
    uses it to price and charge credits (the cost depends on
    revision_intensity × total_questions, which are only known post-parse);
    raising from it aborts the pipeline before the expensive part.

    Modes:
      * fresh       — parse the query and generate
      * remediation — `wrong_items` (from the frontend) feed the Parser
      * review      — Analyzer builds a mastery profile first, which the Parser
                      uses to target weak knowledge points

    `revision_intensity` is NOT a parameter — the Parser's LLM infers it from
    the query wording (Spec B §3.4). The caller never sets it.
    """
    from ai_engine import parser, retriever, reviser

    # 1. review mode: build the mastery profile first
    profile: MasteryProfile | None = None
    if mode == "review":
        if not user_id:
            raise ParserError("mode=review requires user_id")
        profile = build_profile(user_id, review_window_days)

    # 2. Parser: user_query (+ context) → GenerateRequest
    req: GenerateRequest = parser.parse(
        user_query,
        mode=mode,
        wrong_items=wrong_items,
        mastery=profile,
    )
    req.user_id = user_id
    req.review_window_days = review_window_days
    if on_request is not None:
        on_request(req)

    # 3. Retriever: GenerateRequest → candidate pool (+ shortfall)
    retrieval = retriever.retrieve(req)

    # 4. Reviser: candidates + request → Paper
    #    (Reviser reads retrieval.shortfall to decide whether to fresh-fill
    #     gaps, honouring req.revision_intensity — Spec B §5.)
    paper: Paper = reviser.build_paper(req, retrieval)

    return paper


# ─────────────────────────────────────────────────────────────────────────────
# revise_paper — review iteration (Spec B §8)
# ─────────────────────────────────────────────────────────────────────────────
def revise_paper(
    current_paper: Paper,
    user_instruction: str,
    on_request: Callable[[GenerateRequest], None] | None = None,
) -> Paper:
    """Apply a natural-language revision instruction to an existing paper,
    returning a brand-new Paper (fresh paper_id). Stateless: everything comes
    from the arguments; the backend supplies `current_paper` (read from its
    `papers` table).

    Orchestration mirrors generate_paper — Parser(instruction + original
    context) → Retriever → Reviser — since a revision is just a new request
    seeded with what the current paper already is. The new paper records
    `metadata.revised_from` so the frontend can link back to the original.
    """
    from ai_engine import parser, retriever, reviser

    # Give the Parser the original paper's shape as context, so a relative
    # instruction ("把选择题换成词形转换") resolves against the real paper.
    orig = current_paper.request
    context_parts = [f"共 {orig.total_questions} 题"]
    if orig.question_types:
        context_parts.append(
            "题型：" + "、".join(QUESTION_TYPE_LABELS.get(t, t) for t in orig.question_types)
        )
    if orig.knowledge_points:
        context_parts.append("考点：" + "、".join(orig.knowledge_points))
    if orig.free_text:
        context_parts.append(f"主题：{orig.free_text}")

    query = (
        "这是在一份已有试卷基础上的修改请求。\n"
        f"原试卷：{'；'.join(context_parts)}。\n"
        f"用户的修改要求：{user_instruction}\n"
        "请在原试卷基础上应用修改要求，输出修改后完整的出题需求。"
    )

    req: GenerateRequest = parser.parse(query, mode="fresh")
    req.user_id = orig.user_id
    req.review_window_days = orig.review_window_days
    if on_request is not None:
        on_request(req)

    retrieval = retriever.retrieve(req)
    paper: Paper = reviser.build_paper(req, retrieval)
    paper.metadata["revised_from"] = current_paper.paper_id
    return paper


# ─────────────────────────────────────────────────────────────────────────────
# generate_solution — standalone (Spec B §6)
# ─────────────────────────────────────────────────────────────────────────────
def generate_solution(
    q: RevisedQuestion,
    *,
    source_question_id: str | None = None,
    revision_mode: RevisionMode | None = None,
    user_answer: str | list[str] | dict[str, str] | None = None,
) -> str:
    """Generate an explanation for one question, on demand. Every call hits
    the LLM (no cache); when user_answer is given it also explains why that
    wrong choice is incorrect."""
    from ai_engine import solutioner

    return solutioner.generate_solution(
        q,
        source_question_id=source_question_id,
        revision_mode=revision_mode,
        user_answer=user_answer,
    )


# ─────────────────────────────────────────────────────────────────────────────
# build_profile — standalone (Spec B §7)
# ─────────────────────────────────────────────────────────────────────────────
def build_profile(user_id: str, window_days: int | None = None) -> MasteryProfile:
    """User's mastery profile from attempt history. Read-only, no LLM."""
    from ai_engine import analyzer

    return analyzer.build_profile(user_id, window_days)


def build_site_profile(window_days: int | None = None) -> MasteryProfile:
    """Site-wide mastery profile across all users. Read-only, no LLM."""
    from ai_engine import analyzer

    return analyzer.build_site_profile(window_days)
