"""Turn retrieved bank questions into a paper while preserving API fields."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from uuid import uuid4

from shared.schemas import GenerateRequest, Paper, PaperItem, Question, RetrievalResult, RevisedQuestion


def _copy(question: Question) -> RevisedQuestion:
    return RevisedQuestion(stem=question.stem, question_type=question.question_type, options=question.options, hint=question.hint, original_sentence=question.original_sentence, instruction=question.instruction, template=question.template, answer=question.answer, solution=question.solution, knowledge_point_ids=question.knowledge_point_ids)


def _valid(original: Question, revised: RevisedQuestion) -> bool:
    if revised.question_type != original.question_type or set(revised.knowledge_point_ids) != set(original.knowledge_point_ids):
        return False
    if original.question_type == "single_choice":
        return bool(revised.options and len(revised.options) == 4 and {x.label for x in revised.options} == {"A", "B", "C", "D"} and revised.answer in {"A", "B", "C", "D"})
    return bool(revised.answer)


def _revise(question: Question, request: GenerateRequest) -> RevisedQuestion:
    if request.revision_intensity == "original":
        return _copy(question)
    prompt = ("Revise this English middle-school exam question. Return only the requested JSON. "
              "Keep question_type and knowledge_point_ids unchanged. For single choice, return exactly four A-D options and an answer equal to one label.\n"
              f"User preference: {request.free_text or 'ordinary practice'}\nOriginal question: {question.model_dump_json()}")
    try:
        from shared.llm.deepseek import get_llm_client
        revised = get_llm_client().structured(response_model=RevisedQuestion, prompt=prompt, max_retries=2, temperature=0.5 if request.revision_intensity == "fresh" else 0.3)
        return revised if _valid(question, revised) else _copy(question)
    except Exception:
        return _copy(question)


def build_paper(request: GenerateRequest, retrieval: RetrievalResult) -> Paper:
    selected = retrieval.items[:request.total_questions]
    items: list[PaperItem] = []
    with ThreadPoolExecutor(max_workers=min(4, len(selected) or 1)) as pool:
        futures = {pool.submit(_revise, item.question, request): (index, item.question) for index, item in enumerate(selected, 1)}
        for future in as_completed(futures):
            index, source = futures[future]
            items.append(PaperItem(index=index, question=future.result(), score=5, source_question_id=source.id, revision_mode=request.revision_intensity))
    items.sort(key=lambda item: item.index)
    return Paper(paper_id=uuid4().hex, title=f"中考英语{request.total_questions}道练习", generated_at=datetime.now(timezone.utc), request=request, items=items, total_score=sum(item.score for item in items), metadata={"engine": "parser-retriever-reviser", "llm_calls": len(items) if request.revision_intensity != "original" else 0, "retrieval_warnings": retrieval.warnings, "retrieval_shortfall": retrieval.shortfall})
