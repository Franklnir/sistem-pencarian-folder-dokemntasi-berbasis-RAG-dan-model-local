import re
from typing import List, Dict, Any, Optional
from rank_bm25 import BM25Okapi
from app.database.repository import get_repository


def tokenize(text: str) -> List[str]:
    """Simple alphanumeric tokenizer supporting Indonesian and English."""
    return re.findall(r"\w+", text.lower())


class LexicalRetriever:
    _cached_bm25: Optional[BM25Okapi] = None
    _cached_chunks: Optional[List[Dict[str, Any]]] = None

    def __init__(self):
        self.repo = get_repository()

    @classmethod
    def invalidate_cache(cls):
        cls._cached_bm25 = None
        cls._cached_chunks = None

    def _ensure_cache(self):
        if LexicalRetriever._cached_bm25 is None or LexicalRetriever._cached_chunks is None:
            chunks = self.repo.get_all_chunks_for_lexical()
            if not chunks:
                LexicalRetriever._cached_chunks = []
                LexicalRetriever._cached_bm25 = None
                return
            corpus_tokens = [tokenize(c["text"]) for c in chunks]
            LexicalRetriever._cached_chunks = chunks
            LexicalRetriever._cached_bm25 = BM25Okapi(corpus_tokens)

    def search(
        self,
        query: str,
        limit: int = 50,
        extensions: Optional[List[str]] = None,
        folder_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Runs BM25 lexical search over indexed document chunks using cached BM25 model.
        Returns a list of candidate dictionaries with lexical ranks and scores.
        """
        query_tokens = tokenize(query)
        if not query_tokens:
            return []

        self._ensure_cache()
        bm25 = LexicalRetriever._cached_bm25
        chunks = LexicalRetriever._cached_chunks

        if not bm25 or not chunks:
            return []

        doc_scores = bm25.get_scores(query_tokens)

        folder_prefix = None
        if folder_id:
            folder = self.repo.get_folder_by_id(folder_id)
            if folder:
                folder_prefix = folder.path.rstrip("\\/") + "\\"

        ext_set = set(e.lower() for e in extensions) if extensions else None

        scored_candidates = []
        for idx, score in enumerate(doc_scores):
            if score > 0:
                c = chunks[idx]
                if ext_set and c.get("extension", "").lower() not in ext_set:
                    continue
                if folder_prefix and not c.get("path", "").startswith(folder_prefix):
                    continue
                cand = dict(c)
                cand["score"] = float(score)
                scored_candidates.append(cand)

        scored_candidates.sort(key=lambda x: x["score"], reverse=True)
        top_candidates = scored_candidates[:limit]

        # Assign 1-based ranks
        for rank, cand in enumerate(top_candidates, start=1):
            cand["lexical_rank"] = rank

        return top_candidates
