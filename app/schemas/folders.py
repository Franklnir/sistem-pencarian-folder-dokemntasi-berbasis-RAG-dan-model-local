from datetime import datetime
from pydantic import BaseModel, Field, field_validator
from app.config import canonicalize_path, is_critical_system_directory
from pathlib import Path


class FolderCreateRequest(BaseModel):
    path: str = Field(..., min_length=2, description="Absolute Windows folder path to monitor")

    @field_validator("path")
    @classmethod
    def validate_folder_path(cls, v: str) -> str:
        canon = canonicalize_path(v)
        p = Path(canon)
        if not p.exists():
            raise ValueError(f"Folder path does not exist: {v}")
        if not p.is_dir():
            raise ValueError(f"Specified path is not a directory: {v}")
        if is_critical_system_directory(canon):
            raise ValueError("Monitoring critical Windows system directories is disallowed.")
        return canon


class FolderUpdateRequest(BaseModel):
    enabled: bool


class FolderResponse(BaseModel):
    id: int
    path: str
    enabled: bool
    created_at: datetime
    updated_at: datetime
