"""Schemas for chunked/resumable file upload API."""
from typing import Any, List, Optional

from pydantic import BaseModel, Field


class ChunkedUploadInitRequest(BaseModel):
    """Request to initiate a chunked upload session."""
    filename: str = Field(..., min_length=1, description="Original file name")
    total_size: int = Field(..., gt=0, le=10_000_000_000, description="Total file size in bytes")
    total_chunks: int = Field(..., gt=0, le=2000, description="Number of chunks")
    chunk_size: int = Field(..., gt=0, le=50_000_000, description="Bytes per chunk (last may be smaller)")


class ChunkedUploadInitResponse(BaseModel):
    """Response after initiating upload session."""
    upload_id: str
    chunk_size: int
    total_chunks: int
    uploaded_chunks: List[int] = Field(default_factory=list, description="Chunk indices already received (for resume)")


class ChunkedUploadStatusResponse(BaseModel):
    """Status of an in-progress chunked upload."""
    upload_id: str
    filename: str
    total_size: int
    total_chunks: int
    chunk_size: int = 0
    uploaded_chunks: List[int]
    status: str = Field(..., description="pending|uploading|merging|processing|completed|failed")
    progress_pct: float = 0.0
    processing_pct: Optional[float] = None  # RIM-OS progress when status=processing (0-100)
    error: Optional[str] = None
    result: Optional[dict] = None  # Full audit result when status=completed


class ChunkedUploadCompleteResponse(BaseModel):
    """Response when all chunks received and audit complete."""
    upload_id: str
    file_info: dict[str, Any]
    kpis: list[dict[str, Any]]
    verification: dict[str, Any]
    file_hash: str
    metadata: dict[str, Any]
