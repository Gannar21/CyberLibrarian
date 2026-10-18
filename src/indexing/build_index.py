"""Load documents, create chunks, and build both search indexes."""

import argparse
import json

from src.common.config import Config
from src.common.schemas import Document
from src.indexing.chunker import chunk_document
from src.indexing.bm25_index import save_bm25_index
from src.indexing.vector_index import build_vector_index


def load_documents(file_path):
    """Load documents from a JSONL file."""

    documents = []

    with file_path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue

            try:
                document = Document.from_jsonl(line)
                documents.append(document)
            except Exception as exc:
                raise ValueError(
                    f"Invalid document at line {line_number} "
                    f"in {file_path}: {exc}"
                ) from exc

    return documents


def main():
    """Build and save the BM25 and vector indexes."""

    parser = argparse.ArgumentParser(
        description="Build the CyberLibrarian search indexes."
    )
    parser.add_argument(
        "--sample",
        action="store_true",
        help="Use the sample documents instead of the full corpus.",
    )
    args = parser.parse_args()

    # Select the input file.
    input_file = (
        Config.SAMPLE_JSONL
        if args.sample
        else Config.DOCUMENTS_JSONL
    )

    if not input_file.exists():
        raise FileNotFoundError(
            f"Documents file not found: {input_file}\n"
            "Make sure the ingestion pipeline has created the file."
        )

    print(f"Loading documents from: {input_file}")
    documents = load_documents(input_file)

    if not documents:
        raise ValueError("No documents were found in the input file.")

    print(f"Loaded {len(documents)} documents.")

    # Split each document into chunks.
    chunks = []

    for document in documents:
        chunks.extend(chunk_document(document))

    if not chunks:
        raise ValueError("No chunks were created.")

    print(f"Created {len(chunks)} chunks.")

    # Build and save the BM25 keyword index.
    print("Building BM25 index...")
    save_bm25_index(chunks)
    print(f"BM25 index saved to: {Config.BM25_INDEX}")

    # Build and save the ChromaDB vector index.
    print("Building vector index...")
    build_vector_index(chunks)
    print(f"Vector index saved to: {Config.VECTOR_INDEX_DIR}")

    print("\nIndexing completed successfully!")
    print(f"Documents: {len(documents)}")
    print(f"Chunks: {len(chunks)}")


if __name__ == "__main__":
    main()