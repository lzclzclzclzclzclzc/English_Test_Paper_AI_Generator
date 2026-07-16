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
writes no SQL (Solutioner's solution cache is the one exception). Persistence
is the backend's job (Spec C).
"""
from __future__ import annotations

from ai_engine.errors import ParserError
from shared.schemas import (
    GenerateMode,
    GenerateRequest,
    MasteryProfile,
    Paper,
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
) -> Paper:
    """Natural-language request → a full Paper.

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
def revise_paper(current_paper: Paper, user_instruction: str) -> Paper:
    """Apply a natural-language revision instruction to an existing paper,
    returning a brand-new Paper (fresh paper_id). Stateless: everything comes
    from the arguments; the backend supplies `current_paper` (read from its
    `papers` table).
    """
    from ai_engine import reviser

    return reviser.revise_paper(current_paper, user_instruction)


# ─────────────────────────────────────────────────────────────────────────────
# generate_solution — standalone (Spec B §6)
# ─────────────────────────────────────────────────────────────────────────────
def generate_solution(
    q: RevisedQuestion,
    *,
    source_question_id: str | None = None,
    revision_mode: RevisionMode | None = None,
) -> str:
    """Generate an explanation for one question, on demand. Caches back to the
    bank only when the question is an untouched original (Spec A §2.6 #6)."""
    from ai_engine import solutioner

    return solutioner.generate_solution(
        q,
        source_question_id=source_question_id,
        revision_mode=revision_mode,
    )


# ─────────────────────────────────────────────────────────────────────────────
# build_profile — standalone (Spec B §7)
# ─────────────────────────────────────────────────────────────────────────────
def build_profile(user_id: str, window_days: int | None = None) -> MasteryProfile:
    """User's mastery profile from attempt history. Read-only, no LLM."""
    from ai_engine import analyzer

    return analyzer.build_profile(user_id, window_days)
