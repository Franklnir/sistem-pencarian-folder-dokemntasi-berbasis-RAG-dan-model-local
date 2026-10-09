from typing import List, Dict, Any, Optional
from app.database.repository import get_repository
from app.embedding.model import get_embedding_manager


class SemanticRetriever:
    def __init__(self):
        self.repo = get_repository()
        self.embedder = get_embedding_manager()

    def search(
        self,
        query: str,
        limit: int = 50,
        extensions: Optional[List[str]] = None,
        folder_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Runs vector similarity search using query embedding against document_chunks.
        Returns candidates ranked with vector_rank and cosine similarity score.
        """
        query_vec = self.embedder.encode_query(query)
        candidates = self.repo.vector_search(
            query_embedding=query_vec,
            top_k=limit,
            extensions=extensions,
            folder_id=folder_id
        )

        for rank, cand in enumerate(candidates, start=1):
            cand["vector_rank"] = rank

        return candidates
