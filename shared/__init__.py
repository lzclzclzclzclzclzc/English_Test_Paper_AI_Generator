"""Shared layer: the single dependency crossing-point between subsystems.

Re-exports every data contract from `schemas` so downstream code can write
`from shared import Question, GenerateRequest, ...` without reaching into the
submodule. Future additions (storage.py, embedding.py, config.py, llm/) will be
re-exported here too.
"""
from shared.schemas import (
    # aliases
    Answer,
    BlankGroup,
    GenerateMode,
    QuestionType,
    RevisionMode,
    VECTOR_INDEXED_QUESTION_TYPES,
    # question bank
    KnowledgePoint,
    Option,
    Question,
    # generation
    GenerateRequest,
    WrongItemRef,
    # retrieval
    RetrievalResult,
    RetrievedItem,
    # paper
    Paper,
    PaperItem,
    RevisedQuestion,
    # attempts & mastery
    Attempt,
    AttemptItem,
    KPMastery,
    MasteryProfile,
)

__all__ = [
    "Answer",
    "BlankGroup",
    "GenerateMode",
    "QuestionType",
    "RevisionMode",
    "VECTOR_INDEXED_QUESTION_TYPES",
    "KnowledgePoint",
    "Option",
    "Question",
    "GenerateRequest",
    "WrongItemRef",
    "RetrievalResult",
    "RetrievedItem",
    "Paper",
    "PaperItem",
    "RevisedQuestion",
    "Attempt",
    "AttemptItem",
    "KPMastery",
    "MasteryProfile",
]
