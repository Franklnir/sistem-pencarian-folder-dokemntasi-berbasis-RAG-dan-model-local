from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel


class FileDetailResponse(BaseModel):
    id: int
    filename: str
    path: str
    extension: str
    size_bytes: int
    modified_at: datetime
    content_hash: str
    status: str
    error_message: Optional[str] = None
    indexed_at: Optional[datetime] = None


class FileListResponse(BaseModel):
    page: int
    page_size: int
    total: int
    items: List[FileDetailResponse]


class ReindexFileResponse(BaseModel):
    job_id: str
    file_id: int
    status: str


class RebuildRequest(BaseModel):
    confirm: bool = False
    scope: str = "all"


class RebuildResponse(BaseModel):
    status: str
    message: str


class ResumeResponse(BaseModel):
    status: str
    count: int
