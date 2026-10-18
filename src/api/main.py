"""
Owner: Person 4 (Generation / API)

This module must expose a FastAPI application with at minimum:

    POST /ask
        Request body:  { "question": str, "filters": dict | None }
        Response body: AnswerResponse (see src.common.schemas)

The handler should call src.generation.answer.answer() and return the result.
Include a GET /health endpoint that returns {"status": "ok"}.

Relevant signatures (from src.common.schemas):
    class AnswerResponse(BaseModel):
        answer: str
        citations: list[Citation]
        chunks: list[RetrievalResult]
        latency_ms: int
        tokens: int
        cost: float
        answerable: bool

Usage (once implemented):
    uvicorn src.api.main:app --reload

Note: app/client.py posts to API_URL + "/ask" and expects the AnswerResponse
JSON shape; do not change the route or response model.
"""
raise NotImplementedError("main.py must be implemented by Person 4")
