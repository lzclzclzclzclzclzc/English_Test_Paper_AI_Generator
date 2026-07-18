from unittest.mock import MagicMock

from ai_engine.solutioner import generate_solution
from shared.schemas import Option, RevisedQuestion


def test_original_solution_is_generated_and_cached(monkeypatch):
    question = RevisedQuestion(
        question_type="single_choice",
        stem="Choose.",
        options=[Option(label="A", text="a"), Option(label="B", text="b"), Option(label="C", text="c"), Option(label="D", text="d")],
        answer="A",
        knowledge_point_ids=["kp_1"],
    )
    client = MagicMock()
    client.text.return_value = "关键考点：test\n解题思路：test\n易错点：test"
    monkeypatch.setattr("shared.llm.deepseek.get_llm_client", lambda: client)
    cache = MagicMock(return_value=True)
    monkeypatch.setattr("ai_engine.solutioner.storage.write_question_solution", cache)

    result = generate_solution(question, source_question_id="q_1", revision_mode="original")

    assert result.startswith("关键考点")
    cache.assert_called_once_with("q_1", result)
