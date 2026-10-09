import time
from fastapi import APIRouter
from app.retrieval.hybrid import HybridRetriever
from app.schemas.search import SearchRequest, SearchResponse, SearchResultItem

router = APIRouter(prefix="/api/search", tags=["search"])
hybrid_retriever = HybridRetriever()


@router.post("", response_model=SearchResponse)
def search_documents(payload: SearchRequest):
    """
    Hybrid semantic + lexical document search using Reciprocal Rank Fusion (RRF).
    """
    start_time = time.perf_counter()

    results = hybrid_retriever.search(
        query=payload.query,
        top_k=payload.top_k,
        extensions=payload.extensions,
        folder_id=payload.folder_id
    )

    took_ms = round((time.perf_counter() - start_time) * 1000.0, 2)

    NOISE_FILENAMES = {
        "top_level.txt", "sha256sums.txt", "cmakelists.txt", "cmakecache.txt",
        "targetdirectories.txt", "labels.txt", "exclude.txt", "license.txt",
        "do_not_use_on_4mb.txt"
    }

    clean_results = [
        r for r in results 
        if r["filename"].lower() not in NOISE_FILENAMES
    ]

    return SearchResponse(
        query=payload.query,
        took_ms=took_ms,
        results=[
            SearchResultItem(
                file_id=r["file_id"],
                filename=r["filename"],
                path=r["path"],
                extension=r["extension"],
                score=r["score"],
                match_type=r["match_type"],
                page_no=r["page_no"],
                snippet=r["snippet"]
            )
            for r in clean_results
        ]
    )
