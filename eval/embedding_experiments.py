
"""Compare embedding models using isolated vector and BM25 indexes."""

import json
import time
from pathlib import Path
from unittest.mock import patch

from src.common.config import Config
from src.indexing.build_index import load_documents
from src.indexing.chunker import chunk_document
from src.indexing.bm25_index import save_bm25_index
from src.indexing.vector_index import build_vector_index, get_embedding_model
from src.retrieval import backend
from eval.retrieval_eval import load_questions, run_config, to_markdown


QUESTIONS_PATH = "data/eval/questions_dev.jsonl"
OUTPUT_DIR = Path("eval/results/embedding_experiments")
INDEX_ROOT = Path("indexes/embedding_experiments")

CHUNK_SIZE = 512
CHUNK_OVERLAP = 64

MODELS = [
    ("baseline_minilm_l6", "all-MiniLM-L6-v2"),
    ("candidate_minilm_l3", "paraphrase-MiniLM-L3-v2"),
]


def clear_backend_caches():
    backend._bm25_index.cache_clear()
    backend._collection.cache_clear()
    backend.all_chunks.cache_clear()


def build_experiment(name, model_name, documents):
    """Build isolated indexes using one embedding model."""

    chunks = []
    for document in documents:
        chunks.extend(
            chunk_document(
                document,
                chunk_size=CHUNK_SIZE,
                chunk_overlap=CHUNK_OVERLAP,
            )
        )

    experiment_dir = INDEX_ROOT / name
    bm25_path = experiment_dir / "bm25.pkl"
    vector_path = experiment_dir / "chroma"

    print(f"\nBuilding {name}")
    print(f"Embedding model: {model_name}")
    print(f"Chunk size: {CHUNK_SIZE}; overlap: {CHUNK_OVERLAP}")
    print(f"Chunks: {len(chunks)}")

    save_bm25_index(chunks, index_path=bm25_path)

    # The model used to build the vector index must also be used at query time.
    with patch.object(Config, "EMBEDDING_MODEL", model_name):
        build_vector_index(chunks, persist_directory=vector_path)

    return chunks, bm25_path, vector_path


def evaluate_experiment(name, model_name, chunks, bm25_path, vector_path, questions):
    """Evaluate with the same model and isolated indexes."""

    clear_backend_caches()

    try:
        with (
            patch.object(Config, "BM25_INDEX", bm25_path),
            patch.object(Config, "VECTOR_INDEX_DIR", vector_path),
            patch.object(Config, "EMBEDDING_MODEL", model_name),
        ):
            clear_backend_caches()

            row, failures = run_config(
                name,
                questions,
                mode="hybrid",
            )

        row["chunk_count"] = len(chunks)
        row["embedding_model"] = model_name
        row["chunk_size"] = CHUNK_SIZE
        row["chunk_overlap"] = CHUNK_OVERLAP

        return row, failures

    finally:
        clear_backend_caches()


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    questions = load_questions(QUESTIONS_PATH)
    if not questions:
        raise RuntimeError(f"No answerable questions found in {QUESTIONS_PATH}")

    documents = load_documents(Config.DOCUMENTS_JSONL)

    print(f"Documents: {len(documents)}")
    print(f"Development questions: {len(questions)}")

    rows = []
    all_failures = []

    for name, model_name in MODELS:
        chunks, bm25_path, vector_path = build_experiment(
            name, model_name, documents
        )

        row, failures = evaluate_experiment(
            name,
            model_name,
            chunks,
            bm25_path,
            vector_path,
            questions,
        )

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

    print("\n=== Embedding Experiment Results ===")
    print(to_markdown(rows))
    print(f"\nResults saved to: {results_path}")
    print(f"Failures saved to: {failures_path}")


if __name__ == "__main__":
    main()
