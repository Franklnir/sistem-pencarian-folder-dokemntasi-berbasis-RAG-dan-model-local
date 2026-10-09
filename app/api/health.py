from fastapi import APIRouter
from app.database.repository import get_repository
from app.embedding.model import get_embedding_manager
from app.ingestion.queue import get_queue
from app.ingestion.watcher import get_watcher

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
def get_health():
    """Liveness probe."""
    return {
        "status": "ok",
        "service": "ai-file-search",
        "version": "1.0.0"
    }


@router.get("/status")
def get_status():
    """Detailed system and research status."""
    repo = get_repository()
    watcher = get_watcher()
    embedder = get_embedding_manager()
    queue = get_queue()

    db_stats = repo.get_stats()

    return {
        "service": "running",
        "watcher": "running" if watcher.is_running else "stopped",
        "database": db_stats["database"],
        "embedding_model": "ready" if embedder.is_ready else "loading",
        "model_name": embedder.model_name,
        "indexed_files": db_stats["indexed_files"],
        "indexed_chunks": db_stats["indexed_chunks"],
        "pending_jobs": queue.pending_count,
        "failed_files": db_stats["failed_files"],
        "last_indexed_at": db_stats["last_indexed_at"]
    }
