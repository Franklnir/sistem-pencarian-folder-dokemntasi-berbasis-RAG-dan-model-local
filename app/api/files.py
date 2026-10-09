import os
import json
import asyncio
import queue
import subprocess
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse, FileResponse

from app.config import settings
from app.database.repository import get_repository
from app.ingestion.events import get_event_bus
from app.schemas.files import FileDetailResponse, FileListResponse


router = APIRouter(prefix="/api/files", tags=["files"])


@router.get("/stream")
async def sync_event_stream(request: Request):
    """
    Server-Sent Events (SSE) stream for real-time synchronization with local Windows filesystem.
    Pushes instantaneous updates when files are created, modified, indexed, or deleted.
    """
    event_bus = get_event_bus()
    subscriber_queue = event_bus.subscribe()

    async def event_generator():
        try:
            # Initial handshake
            yield f"event: connected\ndata: {json.dumps({'status': 'online', 'sync': 'active'})}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    # Non-blocking poll from thread-safe queue via to_thread
                    msg = await asyncio.to_thread(subscriber_queue.get, timeout=2.0)
                    yield f"event: {msg['event']}\ndata: {json.dumps(msg['data'])}\n\n"
                except queue.Empty:
                    # Heartbeat comment to keep HTTP connection alive
                    yield ": keep-alive\n\n"
        finally:
            event_bus.unsubscribe(subscriber_queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.get("", response_model=FileListResponse)
def list_files(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    extension: Optional[str] = Query(default=None),
    folder_path: Optional[str] = Query(default=None)
):
    """List indexed files with pagination, folder filtering, and extension filtering."""
    if extension:
        clean_ext = extension.lower() if extension.startswith(".") else f".{extension.lower()}"
        if clean_ext not in settings.ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Extension '{clean_ext}' not in allowed list: {settings.ALLOWED_EXTENSIONS}"
            )
        extension = clean_ext

    repo = get_repository()
    records, total = repo.list_files(page=page, page_size=page_size, extension=extension, folder_path=folder_path)


    return FileListResponse(
        page=page,
        page_size=page_size,
        total=total,
        items=[
            FileDetailResponse(
                id=r.id,
                filename=r.filename,
                path=r.path,
                extension=r.extension,
                size_bytes=r.size_bytes,
                modified_at=r.modified_at,
                content_hash=r.content_hash,
                status=r.status,
                error_message=r.error_message,
                indexed_at=r.indexed_at
            )
            for r in records
        ]
    )


@router.get("/{file_id}", response_model=FileDetailResponse)
def get_file(file_id: int):
    """Get metadata for a specific file by file_id."""
    repo = get_repository()
    rec = repo.get_file_by_id(file_id)
    if not rec:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found.")

    return FileDetailResponse(
        id=rec.id,
        filename=rec.filename,
        path=rec.path,
        extension=rec.extension,
        size_bytes=rec.size_bytes,
        modified_at=rec.modified_at,
        content_hash=rec.content_hash,
        status=rec.status,
        error_message=rec.error_message,
        indexed_at=rec.indexed_at
    )


@router.get("/{file_id}/preview")
def get_file_preview(file_id: int):
    """Get metadata and text preview chunk for the File Explorer preview pane."""
    repo = get_repository()
    preview_data = repo.get_file_preview(file_id)
    if not preview_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found.")

    rec = preview_data["file"]
    return {
        "id": rec.id,
        "filename": rec.filename,
        "path": rec.path,
        "extension": rec.extension,
        "size_bytes": rec.size_bytes,
        "modified_at": rec.modified_at.isoformat() if rec.modified_at else None,
        "content_hash": rec.content_hash,
        "status": rec.status,
        "indexed_at": rec.indexed_at.isoformat() if rec.indexed_at else None,
        "chunk_count": preview_data["chunk_count"],
        "preview_text": preview_data["preview_text"]
    }


@router.post("/{file_id}/open")
def open_file(file_id: int):
    """Open the file in its default Windows desktop application using verified file_id."""
    repo = get_repository()
    rec = repo.get_file_by_id(file_id)
    if not rec:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found.")

    path_obj = Path(rec.path).resolve()
    if not path_obj.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Physical file missing on disk: {rec.path}")

    try:
        os.startfile(str(path_obj))
        return {"status": "ok", "message": f"Opened {rec.filename}", "path": str(path_obj)}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to open file: {str(e)}")


@router.post("/{file_id}/reveal")
def reveal_in_explorer(file_id: int):
    """Highlight and reveal the file in Windows File Explorer using verified file_id."""
    repo = get_repository()
    rec = repo.get_file_by_id(file_id)
    if not rec:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found.")

    path_obj = Path(rec.path).resolve()
    if not path_obj.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Physical file missing on disk: {rec.path}")

    try:
        # On Windows, explorer.exe /select,"C:\full\path" must not wrap /select in quotes
        cmd = f'explorer.exe /select,"{str(path_obj)}"'
        subprocess.Popen(cmd)
        return {"status": "ok", "message": f"Revealed {rec.filename} in explorer", "path": str(path_obj)}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to reveal file: {str(e)}")


@router.get("/{file_id}/download")
def download_or_view_file(file_id: int):
    """Serve the raw document file directly for direct browser view or download."""
    repo = get_repository()
    rec = repo.get_file_by_id(file_id)
    if not rec:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found.")

    path_obj = Path(rec.path).resolve()
    if not path_obj.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Physical file missing on disk: {rec.path}")

    return FileResponse(path=str(path_obj), filename=rec.filename)
