
"""Compare chunk configurations using isolated BM25 and Chroma indexes."""

import json
from pathlib import Path
from unittest.mock import patch

from src.common.config import Config
from src.indexing.build_index import load_documents
from src.indexing.chunker import chunk_document
from src.indexing.bm25_index import save_bm25_index
from src.indexing.vector_index import build_vector_index
from src.retrieval import backend
from eval.retrieval_eval import load_questions, run_config, to_markdown


EXPERIMENTS = [
    ("baseline_512_64", 512, 64),
    ("chunk_256_32", 256, 32),
    ("chunk_384_48", 384, 48),
]

QUESTIONS_PATH = "data/eval/questions_dev.jsonl"
OUTPUT_DIR = Path("eval/results/chunk_experiments")
INDEX_ROOT = Path("indexes/experiments")


def build_experiment(name, size, overlap, documents):
    """Build isolated BM25 and vector indexes."""

    chunks = []

    for document in documents:
        chunks.extend(
            chunk_document(
                document,
                chunk_size=size,
                chunk_overlap=overlap,
            )
        )

    if not chunks:
        raise RuntimeError(f"No chunks created for {name}")

    experiment_dir = INDEX_ROOT / name
    bm25_path = experiment_dir / "bm25.pkl"
    vector_path = experiment_dir / "chroma"

    print(f"\nBuilding {name}: size={size}, overlap={overlap}")
    print(f"Chunk count: {len(chunks)}")

    save_bm25_index(chunks, index_path=bm25_path)
    build_vector_index(chunks, persist_directory=vector_path)

    return chunks, bm25_path, vector_path


def evaluate_experiment(name, chunks, bm25_path, vector_path, questions):
    """Evaluate using the isolated experiment indexes."""

    backend._bm25_index.cache_clear()
    backend._collection.cache_clear()
    backend.all_chunks.cache_clear()

    try:
        with (
            patch.object(Config, "BM25_INDEX", bm25_path),
            patch.object(Config, "VECTOR_INDEX_DIR", vector_path),
        ):
            backend._bm25_index.cache_clear()
            backend._collection.cache_clear()
            backend.all_chunks.cache_clear()

            row, failures = run_config(
                name,
                questions,
                mode="hybrid",
            )

        row["chunk_count"] = len(chunks)
        return row, failures

    finally:
        backend._bm25_index.cache_clear()
        backend._collection.cache_clear()
        backend.all_chunks.cache_clear()


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    questions = load_questions(QUESTIONS_PATH)
    if not questions:
        raise RuntimeError(f"No questions found in {QUESTIONS_PATH}")

    documents = load_documents(Config.DOCUMENTS_JSONL)
    print(f"Documents: {len(documents)}")
    print(f"Development questions: {len(questions)}")
    print(f"Embedding model: {Config.EMBEDDING_MODEL}")

    rows = []
    all_failures = []

    for name, size, overlap in EXPERIMENTS:
        chunks, bm25_path, vector_path = build_experiment(
            name, size, overlap, documents
        )

        row, failures = evaluate_experiment(
            name, chunks, bm25_path, vector_path, questions
        )

        row["chunk_size"] = size
        row["chunk_overlap"] = overlap
        row["embedding_model"] = Config.EMBEDDING_MODEL

        rows.append(row)
        all_failures.extend(failures)

        print("\nCurrent result:")
        print(to_markdown([row]))

    results_path = OUTPUT_DIR / "results.json"
    results_path.write_text(
        json.dumps(rows, indent=2),
        encoding="utf-8",
    )

    failures_path = OUTPUT_DIR / "failures.jsonl"
    failures_path.write_text(
        "\n".join(json.dumps(item) for item in all_failures),
        encoding="utf-8",
    )

    print("\n=== Chunk Experiment Results ===")
    print(to_markdown(rows))
    print(f"\nResults saved to: {results_path}")
    print(f"Failures saved to: {failures_path}")


if __name__ == "__main__":
    main()
