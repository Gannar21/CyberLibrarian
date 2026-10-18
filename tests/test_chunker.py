from src.common.schemas import Document
from src.indexing.chunker import chunk_document


def test_chunk_document():
    doc = Document(
        doc_id="test-doc",
        title="Test Document",
        source="owasp",
        section="Introduction",
        date=None,
        url="https://example.com",
        text=" ".join(f"word{i}" for i in range(1200)),
    )

    chunks = chunk_document(doc, chunk_size=512, chunk_overlap=64)

    assert len(chunks) == 3
    assert len(chunks[0].text.split()) == 512
    assert len(chunks[1].text.split()) == 512
    assert len(chunks[2].text.split()) == 304

    # Verify the 64-word overlap.
    assert chunks[0].text.split()[-64:] == chunks[1].text.split()[:64]

    # Verify positions and metadata.
    assert [chunk.position for chunk in chunks] == [0, 1, 2]
    assert chunks[0].doc_id == doc.doc_id
    assert chunks[0].title == doc.title