from fastapi import APIRouter, HTTPException, status
from app.database.repository import get_repository
from app.ingestion.queue import get_queue
from app.schemas.files import (
    ReindexFileResponse,
    RebuildRequest,
    RebuildResponse,
    ResumeResponse
)

router = APIRouter(prefix="/api/index", tags=["indexing"])


@router.post("/file/{file_id}", response_model=ReindexFileResponse)
def reindex_single_file(file_id: int):
    """Reindexes a single file by file_id."""
    repo = get_repository()
    rec = repo.get_file_by_id(file_id)
    if not rec:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found.")

    queue = get_queue()
    job_id = queue.push("REINDEX", rec.path)

    return ReindexFileResponse(
        job_id=job_id,
        file_id=rec.id,
        status="QUEUED"
    )


@router.post("/rebuild", response_model=RebuildResponse)
def trigger_rebuild(payload: RebuildRequest):
    """Triggers a full asynchronous reindex across all files in monitored folders."""
    if not payload.confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rebuild operation requires 'confirm: true'."
        )

    from app.ingestion.watcher import get_watcher
    watcher = get_watcher()
    watcher.sync_monitored_folders()

    return RebuildResponse(
        status="QUEUED",
        message="Full incremental reindex triggered asynchronously."
    )


@router.post("/resume", response_model=ResumeResponse)
def resume_failed_jobs():
    """Resumes failed or pending files by re-enqueuing them."""
    repo = get_repository()
    queue = get_queue()

    records, _ = repo.list_files(page=1, page_size=500)
    resumed_count = 0
    for r in records:
        if r.status in ("FAILED", "PENDING"):
            queue.push("REINDEX", r.path)
            resumed_count += 1

    return ResumeResponse(
        status="QUEUED",
        count=resumed_count
    )


@router.get("/job/{job_id}")
def get_job_status(job_id: str):
    """Retrieve execution status and metrics for a background job."""
    queue = get_queue()
    job = queue.get_job(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")

    return {
        "job_id": job.job_id,
        "path": job.path,
        "event_type": job.event_type,
        "status": job.status,
        "duration_ms": job.duration_ms,
        "error_code": job.error_code
    }

