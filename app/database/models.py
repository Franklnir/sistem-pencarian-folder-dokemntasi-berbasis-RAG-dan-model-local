from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class FileRecord(BaseModel):
    id: Optional[int] = None
    path: str
    filename: str
    extension: str
    size_bytes: int = 0
    modified_at: datetime = Field(default_factory=datetime.utcnow)
    content_hash: str
    status: str = "PENDING"  # PENDING, PROCESSING, INDEXED, FAILED, DELETED
    error_message: Optional[str] = None
    indexed_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ChunkRecord(BaseModel):
    id: Optional[int] = None
    file_id: int
    page_no: Optional[int] = None
    chunk_index: int
    text: str
    embedding: List[float]
    token_count: Optional[int] = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)


class MonitoredFolderRecord(BaseModel):
    id: Optional[int] = None
    path: str
    enabled: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
