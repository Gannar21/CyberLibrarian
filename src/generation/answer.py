"""
Owner: Person 4 (Generation)

This module must call the LLM with the prompt from src.generation.prompt,
parse citation markers ([1], [2], …) from the response, build Citation objects,
and return a fully populated AnswerResponse.

Relevant signatures (from src.common.schemas):
    class Citation(BaseModel):
        id: int
        chunk_id: str
        title: str
        source: str
        section: str
        url: str

    class AnswerResponse(BaseModel):
        answer: str                        # LLM text with [1] [2] markers
        citations: list[Citation]
        chunks: list[RetrievalResult]      # raw retrieval results for the UI
        latency_ms: int
        tokens: int
        cost: float
        answerable: bool                   # False when the model says I don't know

    def answer(
        question: str,
        filters: dict | None = None,
    ) -> AnswerResponse: ...              # stub in src.common.schemas

Required public interface (implement the stub declared in schemas.py):
    def answer(
        question: str,
        filters: dict | None = None,
    ) -> AnswerResponse:
        \"\"\"Run the full RAG pipeline: retrieve → prompt → generate → parse.\"\"\"
        ...
"""
raise NotImplementedError("answer.py must be implemented by Person 4")
