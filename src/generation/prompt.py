"""Owner: Person 4. Builds the prompt sent to the LLM."""
from src.common.schemas import RetrievalResult

NO_ANSWER = "I don't know based on the available documents."

RULES = f"""You are CyberLibrarian, a cybersecurity assistant.
Answer the question using ONLY the numbered sources below.

Rules:
1. Do not use any knowledge from outside the sources.
2. Every sentence of your answer MUST end with the number of the source that supports it, like [1] or [2][3]. An answer without markers is invalid.
3. If none of the sources contains information relevant to the question, reply exactly: {NO_ANSWER} If the sources contain part of the answer, give that part with citations.
4. Keep the answer short and clear."""


def build_prompt(question: str, results: list[RetrievalResult]) -> str:
    """Return a prompt string with numbered sources so the model can cite [1], [2]..."""
    blocks = []
    for i, r in enumerate(results, start=1):
        c = r.chunk
        header = f"[{i}] {c.title}"
        if c.section:
            header += f" - {c.section}"
        header += f" ({c.source.upper()})"
        blocks.append(f"{header}\n{c.text}")

    sources = "\n\n".join(blocks)
    return f"{RULES}\n\nSOURCES:\n{sources}\n\nQUESTION: {question}\n\nANSWER:"