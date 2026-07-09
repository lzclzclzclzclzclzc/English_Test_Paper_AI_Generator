"""AI Engine error hierarchy."""
from __future__ import annotations


class AIEngineError(Exception):
    """Base exception for AI Engine errors."""


class ParserError(AIEngineError):
    """Parser module errors."""


class RetrieverError(AIEngineError):
    """Retriever module errors."""


class ReviserError(AIEngineError):
    """Reviser module errors."""


class SolutionerError(AIEngineError):
    """Solutioner module errors."""


class AnalyzerError(AIEngineError):
    """Analyzer module errors."""
