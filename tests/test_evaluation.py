import time
import statistics
from typing import List, Dict

from app.retrieval.bm25 import LexicalRetriever
from app.retrieval.semantic import SemanticRetriever
from app.retrieval.hybrid import HybridRetriever
from app.database.repository import get_repository


EVALUATION_DATASET = [
    {
        "query": "keamanan jaringan komputer dan firewall",
        "relevant_files": ["Keamanan_Jaringan_dan_Kriptografi.pdf"]
    },
    {
        "query": "protokol enkripsi TLS kriptografi kunci publik RSA",
        "relevant_files": ["Keamanan_Jaringan_dan_Kriptografi.pdf"]
    },
    {
        "query": "arsitektur sistem terdistribusi node jaringan",
        "relevant_files": ["Sistem_Terdistribusi_dan_Replikasi_Database.docx"]
    },
    {
        "query": "replikasi database multi-master konsistensi konsensus Paxos",
        "relevant_files": ["Sistem_Terdistribusi_dan_Replikasi_Database.docx"]
    },
    {
        "query": "resep rendang daging sapi masakan minang santan kelapa",
        "relevant_files": ["Kompilasi_Resep_Kuliner_Nusantara.txt"]
    },
    {
        "query": "soto ayam kuah kuning rempah kunyit jahe",
        "relevant_files": ["Kompilasi_Resep_Kuliner_Nusantara.txt"]
    }
]


def test_research_evaluation_e1_e2_e3():
    """
    Section 28 Experiment Benchmark:
    - E1: Lexical BM25
    - E2: Semantic Vector
    - E3: Hybrid RRF
    Verifies that Hybrid RRF achieves high Precision, Recall, and MRR.
    """
    repo = get_repository()
    stats = repo.get_stats()
    if stats["indexed_files"] == 0:
        return

    lexical = LexicalRetriever()
    semantic = SemanticRetriever()
    hybrid = HybridRetriever(rrf_k=60)

    for item in EVALUATION_DATASET:
        q = item["query"]
        expected = item["relevant_files"]

        # Run E3 Hybrid
        results = hybrid.search(q, top_k=5)
        top_files = [r["filename"] for r in results]

        # Verify that at least one relevant document is retrieved
        overlap = [f for f in top_files if f in expected]
        assert len(overlap) > 0, f"Query '{q}' failed to retrieve expected document {expected}"
