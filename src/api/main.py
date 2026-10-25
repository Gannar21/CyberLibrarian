"""FastAPI app. Run: uvicorn src.api.main:app --reload"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from src.common.schemas import AnswerResponse
from src.generation.answer import answer

app = FastAPI(title="CyberLibrarian")


class AskRequest(BaseModel):
    question: str
    filters: dict | None = None
    history: list[dict] | None = None   # previous chat turns: [{"role", "content"}]


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/ask", response_model=AnswerResponse)
def ask(req: AskRequest) -> AnswerResponse:
    if not req.question.strip():
        raise HTTPException(status_code=422, detail="question must not be empty")
    try:
        return answer(req.question, req.filters, req.history)
    except Exception as e:  # keep the UI alive; details go to server logs
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")