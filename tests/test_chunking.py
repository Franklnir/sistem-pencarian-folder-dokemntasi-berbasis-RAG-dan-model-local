from app.chunking.chunker import DocumentChunker


def test_chunking_short_document():
    chunker = DocumentChunker(target_tokens=500, overlap_tokens=75)
    sections = [
        {"text": "Ini adalah dokumen pengujian pendek untuk sistem pencarian.", "page_no": 1}
    ]
    chunks = chunker.chunk_extracted_sections(sections)
    assert len(chunks) == 1
    assert chunks[0].page_no == 1
    assert chunks[0].chunk_index == 0
    assert "pengujian pendek" in chunks[0].text


def test_chunking_long_document_overlap():
    chunker = DocumentChunker(target_tokens=50, overlap_tokens=10)
    # Generate 150 words
    words = [f"word{i}" for i in range(150)]
    long_text = " ".join(words)

    sections = [
        {"text": long_text, "page_no": 2}
    ]
    chunks = chunker.chunk_extracted_sections(sections)
    assert len(chunks) > 1
    assert all(c.page_no == 2 for c in chunks)
    # Check that chunks maintain indices
    for idx, c in enumerate(chunks):
        assert c.chunk_index == idx
