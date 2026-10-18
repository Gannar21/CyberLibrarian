"""Owner: Person 4. FastAPI app exposing POST /ask and GET /health."""
from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from src.common.schemas import AnswerResponse
from src.generation.answer import answer

app = FastAPI(title="CyberLibrarian API")


class AskRequest(BaseModel):
    question: str
    filters: dict | None = None


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/ask", response_model=AnswerResponse)
def ask(req: AskRequest) -> AnswerResponse:
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Question must not be empty.")
    try:
        return answer(req.question, filters=req.filters)
    except RuntimeError as e:  # e.g. missing LLM_API_KEY
        raise HTTPException(status_code=503, detail=str(e))