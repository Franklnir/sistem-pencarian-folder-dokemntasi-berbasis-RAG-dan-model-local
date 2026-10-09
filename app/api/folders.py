from typing import List
from fastapi import APIRouter, HTTPException, status
from app.database.repository import get_repository
from app.ingestion.watcher import get_watcher
from app.schemas.folders import FolderCreateRequest, FolderUpdateRequest, FolderResponse

router = APIRouter(prefix="/api/folders", tags=["folders"])


@router.get("", response_model=List[FolderResponse])
def list_folders():
    """List all monitored folders."""
    repo = get_repository()
    folders = repo.get_folders()
    return [
        FolderResponse(
            id=f.id,
            path=f.path,
            enabled=f.enabled,
            created_at=f.created_at,
            updated_at=f.updated_at
        )
        for f in folders
    ]


@router.post("", response_model=FolderResponse, status_code=status.HTTP_201_CREATED)
def add_folder(payload: FolderCreateRequest):
    """Add a new directory to monitor."""
    repo = get_repository()
    existing = repo.get_folder_by_path(payload.path)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Folder is already being monitored: {payload.path}"
        )

    folder = repo.add_folder(payload.path)

    # Sync watcher to dynamically schedule the new folder
    watcher = get_watcher()
    watcher.sync_monitored_folders()

    return FolderResponse(
        id=folder.id,
        path=folder.path,
        enabled=folder.enabled,
        created_at=folder.created_at,
        updated_at=folder.updated_at
    )


@router.patch("/{folder_id}", response_model=FolderResponse)
def update_folder(folder_id: int, payload: FolderUpdateRequest):
    """Enable or disable monitoring for a folder."""
    repo = get_repository()
    folder = repo.update_folder_enabled(folder_id, payload.enabled)
    if not folder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found.")

    watcher = get_watcher()
    watcher.sync_monitored_folders()

    return FolderResponse(
        id=folder.id,
        path=folder.path,
        enabled=folder.enabled,
        created_at=folder.created_at,
        updated_at=folder.updated_at
    )


@router.delete("/{folder_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_folder(folder_id: int):
    """Remove a folder from monitoring (does not delete physical files)."""
    repo = get_repository()
    deleted = repo.delete_folder(folder_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found.")

    watcher = get_watcher()
    watcher.sync_monitored_folders()
    return None


@router.post("/browse")
def browse_folder():
    """Opens native Windows folder picker dialog on the desktop and returns the chosen path."""
    import os
    import sys
    import subprocess

    code = (
        "import tkinter as tk; from tkinter import filedialog; "
        "root = tk.Tk(); root.withdraw(); root.wm_attributes('-topmost', 1); "
        "folder = filedialog.askdirectory(title='Pilih Folder untuk AI File Search'); "
        "root.destroy(); "
        "print(folder if folder else '')"
    )
    try:
        proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=60)
        selected = proc.stdout.strip()
        if selected:
            selected = os.path.normpath(selected)
            return {"status": "ok", "path": selected}
        return {"status": "cancelled", "path": None}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Dialog error: {str(e)}")

