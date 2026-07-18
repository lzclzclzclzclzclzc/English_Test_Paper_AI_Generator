from datetime import datetime, timezone
from unittest.mock import MagicMock

import ai_engine
from ai_engine.pipeline import generate_paper
from shared.schemas import GenerateRequest, Paper, RetrievedItem, RetrievalResult


def test_pipeline_forwards_parser_output(monkeypatch):
    request = GenerateRequest(mode="fresh", total_questions=1, total_score=5, revision_intensity="original")
    retrieval = RetrievalResult(items=[])
    paper = Paper(paper_id="paper", title="title", generated_at=datetime.now(timezone.utc), request=request, items=[], total_score=0)
    parser = MagicMock()
    parser.parse.return_value = request
    retriever = MagicMock()
    retriever.retrieve.return_value = retrieval
    reviser = MagicMock()
    reviser.build_paper.return_value = paper
    monkeypatch.setattr(ai_engine, "parser", parser, raising=False)
    monkeypatch.setattr(ai_engine, "retriever", retriever, raising=False)
    monkeypatch.setattr(ai_engine, "reviser", reviser, raising=False)

    result = generate_paper("one original question")

    assert result is paper
    parser.parse.assert_called_once()
    retriever.retrieve.assert_called_once_with(request)
    reviser.build_paper.assert_called_once_with(request, retrieval)
