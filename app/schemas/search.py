from typing import List, Optional
from pydantic import BaseModel, Field, field_validator
from app.config import settings


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500, description="Natural language search query")
    top_k: int = Field(default=5, ge=1, le=50, description="Number of results to return (1-50)")
    extensions: Optional[List[str]] = Field(default=None, description="Optional extension filters, e.g. ['.pdf']")
    folder_id: Optional[int] = Field(default=None, ge=1, description="Optional folder id to restrict search")

    @field_validator("query")
    @classmethod
    def validate_query(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("Query cannot be empty or whitespace only.")
        return clean

    @field_validator("extensions")
    @classmethod
    def validate_extensions(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if not v:
            return None
        valid = []
        for ext in v:
            clean_ext = ext.strip().lower()
            if not clean_ext.startswith("."):
                clean_ext = f".{clean_ext}"
            if clean_ext not in settings.ALLOWED_EXTENSIONS:
                raise ValueError(f"Extension '{clean_ext}' not in allowed list: {settings.ALLOWED_EXTENSIONS}")
            valid.append(clean_ext)
        return valid


class SearchResultItem(BaseModel):
    file_id: int
    filename: str
    path: str
    extension: str
    score: float
    match_type: str  # "hybrid", "semantic", "lexical"
    page_no: Optional[int] = None
    snippet: str


class SearchResponse(BaseModel):
    query: str
    took_ms: float
    results: List[SearchResultItem]
