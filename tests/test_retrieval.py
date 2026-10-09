from app.retrieval.bm25 import tokenize
from app.retrieval.hybrid import HybridRetriever


def test_tokenize():
    tokens = tokenize("Keamanan Jaringan & Firewall 2026!")
    assert "keamanan" in tokens
    assert "jaringan" in tokens
    assert "firewall" in tokens
    assert "2026" in tokens


def test_hybrid_snippet_generation():
    retriever = HybridRetriever(rrf_k=60)
    full_text = (
        "Dasar-dasar teknik informatika menjelaskan bahwa keamanan jaringan adalah aspek "
        "krusial dalam melindungi integritas server dari serangan siber."
    )
    snippet = retriever._create_snippet(full_text, "keamanan jaringan", max_chars=80)
    assert "keamanan jaringan" in snippet.lower()
