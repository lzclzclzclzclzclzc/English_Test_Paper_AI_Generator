"""AI Engine exception hierarchy.

Kept minimal for now — each module raises its own subclass so the future
FastAPI layer (Spec C) can map them to HTTP status codes uniformly.
"""
from __future__ import annotations


class AIEngineError(Exception):
    """Base for all ai_engine errors."""


class ParserError(AIEngineError):
    """Parser could not turn the user query into a valid GenerateRequest."""


class RetrieverError(AIEngineError):
    """Retrieval could not produce any candidates (e.g. empty hard-filter set)."""


class ReviserError(AIEngineError):
    """Reviser could not build a paper from the retrieval result."""


class AnalyzerError(AIEngineError):
    """Analyzer could not build a mastery profile."""
