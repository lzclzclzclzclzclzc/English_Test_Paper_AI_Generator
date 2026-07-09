class AIEngineError(Exception):
    """Base class for AI engine failures."""


class ParserError(AIEngineError):
    pass


class RetrieverError(AIEngineError):
    pass


class ReviserError(AIEngineError):
    pass


class SolutionerError(AIEngineError):
    pass


class LLMError(AIEngineError):
    pass
