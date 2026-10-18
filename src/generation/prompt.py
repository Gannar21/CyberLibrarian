"""
Owner: Person 4 (Generation)

This module must build the LLM prompt from retrieved chunks.
The prompt must instruct the model to answer *only* from the provided chunks
and to insert citation markers like [1], [2] that correspond to the chunks.

Relevant signatures (from src.common.schemas):
    class Chunk(BaseModel):
        chunk_id: str
        title: str
        source: str
        section: str
        text: str
        url: str

    class RetrievalResult(BaseModel):
        chunk: Chunk
        score: float

Required public interface:
    def build_prompt(
        question: str,
        results: list[RetrievalResult],
    ) -> str:
        \"\"\"Return a prompt string ready to send to the LLM.

        The prompt must include numbered source passages so the model can
        produce inline citation markers [1], [2], etc.
        \"\"\"
        ...
"""
raise NotImplementedError("prompt.py must be implemented by Person 4")
