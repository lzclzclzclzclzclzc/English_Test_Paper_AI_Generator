"""AI-engine orchestration: Parser → Retriever → Reviser."""
from __future__ import annotations

from datetime import datetime, timezone
from time import perf_counter
from typing import Literal
from uuid import uuid4

from shared import storage
from shared.config import get_config
from shared.schemas import MasteryProfile, Option, Paper, PaperItem, RevisedQuestion, WrongItemRef


def generate_paper(user_query: str, mode: Literal["fresh", "remediation", "review"] = "fresh", *, wrong_items: list[WrongItemRef] | None = None, user_id: str | None = None, review_window_days: int | None = None) -> Paper:
    """Generate a paper through the real AI pipeline; persistence stays in backend."""
    # Test databases contain neither an ingested question bank nor an API key.
    # Keep this explicit deterministic fixture path so backend contract tests
    # remain fully offline; development/production always use the real engine.
    if get_config().backend.env == "test":
        return _generate_test_paper(user_query, mode, wrong_items, user_id, review_window_days)
    from ai_engine import parser, retriever, reviser
    profile: MasteryProfile | None = None
    if mode == "review":
        if not user_id:
            from ai_engine.errors import ParserError
            raise ParserError("mode=review requires user_id")
        profile = build_profile(user_id, review_window_days)
    parse_started = perf_counter()
    request = parser.parse(user_query, mode=mode, wrong_items=wrong_items, mastery=profile, user_id=user_id, review_window_days=review_window_days)
    parsed_at = perf_counter()
    retrieval = retriever.retrieve(request)
    retrieved_at = perf_counter()
    paper = reviser.build_paper(request, retrieval)
    finished_at = perf_counter()
    return paper.model_copy(update={"metadata": {**paper.metadata, "stage_ms": {"parser": round((parsed_at - parse_started) * 1000, 2), "retriever": round((retrieved_at - parsed_at) * 1000, 2), "reviser": round((finished_at - retrieved_at) * 1000, 2), "total": round((finished_at - parse_started) * 1000, 2)}, "vector_retrieval": bool(request.free_text.strip())}})


def revise_paper(current_paper: Paper, user_instruction: str) -> Paper:
    if get_config().backend.env != "test":
        from ai_engine import reviser
        return reviser.revise_paper(current_paper, user_instruction)
    """Offline test fixture for the established review endpoint."""
    old = current_paper.model_copy(deep=True)
    return Paper(paper_id=uuid4().hex, title=f"{old.title} (revised)", generated_at=datetime.now(timezone.utc), request=old.request.model_copy(update={"free_text": user_instruction}), items=[item.model_copy(update={"revision_mode": "light", "revision_notes": user_instruction, "question": item.question.model_copy(update={"stem": f"{item.question.stem} [{user_instruction}]"})}, deep=True) for item in old.items], total_score=old.total_score, metadata={**old.metadata, "revised_from": old.paper_id})


def generate_solution(q: RevisedQuestion, *, source_question_id: str | None = None, revision_mode: Literal["fresh", "light", "original"] | None = None) -> str:
    if get_config().backend.env != "test":
        from ai_engine.solutioner import generate_solution as generate_live_solution
        return generate_live_solution(q, source_question_id=source_question_id, revision_mode=revision_mode)
    return q.solution or f"答案是 {q.answer}。题型为 {q.question_type}，请结合题干要求作答。"


def build_profile(user_id: str, window_days: int | None = None) -> MasteryProfile:
    return storage.build_mastery_profile(user_id, window_days)


def _generate_test_paper(user_query: str, mode: Literal["fresh", "remediation", "review"], wrong_items: list[WrongItemRef] | None, user_id: str | None, review_window_days: int | None) -> Paper:
    import re

    count_match = re.search(r"(\d+)", user_query)
    total = max(1, min(20, int(count_match.group(1)))) if count_match else 3
    question_types = ["single_choice", "word_form", "sentence_rewriting"]
    items: list[PaperItem] = []
    for index in range(1, total + 1):
        question_type = question_types[(index - 1) % len(question_types)]
        if question_type == "single_choice":
            question = RevisedQuestion(stem=f"Choose the correct answer for question {index}.", question_type=question_type, options=[Option(label="A", text="go"), Option(label="B", text="goes"), Option(label="C", text="went"), Option(label="D", text="gone")], answer="B", knowledge_point_ids=["kp_single_choice_basic"])
        elif question_type == "word_form":
            question = RevisedQuestion(stem=f"Fill in the blank: He has ___ (write) question {index}.", question_type=question_type, hint="write", answer=[{"blank1": ["written"]}], knowledge_point_ids=["kp_word_form_participle"])
        else:
            question = RevisedQuestion(question_type=question_type, original_sentence="He is too young to go to school.", instruction="保持句意基本不变", template="He is ___ young ___ he cannot go to school.", answer=[{"blank1": ["so"], "blank2": ["that"]}], knowledge_point_ids=["kp_sentence_rewriting_so_that"])
        items.append(PaperItem(index=index, question=question, score=5, source_question_id=f"test_q_{index:04d}", revision_mode="fresh", revision_notes="Offline backend test fixture."))
    from shared.schemas import GenerateRequest
    request = GenerateRequest(mode=mode, question_types=question_types, total_questions=total, total_score=total * 5, revision_intensity="fresh", wrong_items=wrong_items or [], user_id=user_id, review_window_days=review_window_days, free_text=user_query)
    return Paper(paper_id=uuid4().hex, title=f"{mode} test paper", generated_at=datetime.now(timezone.utc), request=request, items=items, total_score=total * 5, metadata={"engine": "offline-test-fixture", "mode": mode})
