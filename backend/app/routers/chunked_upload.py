"""
Chunked upload API for large files (5–10 GB).

Endpoints:
- POST /api/upload/chunked/init    - Initiate upload session
- PUT  /api/upload/chunked/{id}/chunk/{index} - Upload a single chunk
- GET  /api/upload/chunked/{id}/status       - Get upload status (for resume)
- POST /api/upload/chunked/{id}/complete    - Signal completion, trigger merge & audit
"""
from fastapi import APIRouter, File, HTTPException, UploadFile

from app.config import get_settings
from app.logging_config import logger
from app.models.chunked_upload_schemas import (
    ChunkedUploadInitRequest,
    ChunkedUploadInitResponse,
    ChunkedUploadStatusResponse,
    ChunkedUploadCompleteResponse,
)
from app.models.error_schemas import ErrorCode, StructuredError
from app.services.chunked_upload_service import chunked_upload_service

router = APIRouter()
settings = get_settings()


def _structured_error(exc: HTTPException):
    """Preserve structured error format if enabled."""
    if settings.use_structured_errors and isinstance(exc.detail, dict):
        pass
    return exc


@router.post("/upload/chunked/init", response_model=ChunkedUploadInitResponse)
async def chunked_upload_init(req: ChunkedUploadInitRequest):
    """
    Initiate a chunked upload session.
    Returns upload_id and list of already-uploaded chunks (for resumable uploads).
    """
    if not settings.chunk_upload_enabled:
        raise HTTPException(status_code=503, detail="Chunked upload is disabled")
    try:
        upload_id, existing = await chunked_upload_service.create_session(
            filename=req.filename,
            total_size=req.total_size,
            total_chunks=req.total_chunks,
            chunk_size=req.chunk_size,
        )
        return ChunkedUploadInitResponse(
            upload_id=upload_id,
            chunk_size=req.chunk_size,
            total_chunks=req.total_chunks,
            uploaded_chunks=existing,
        )
    except ValueError as e:
        err = StructuredError(code=ErrorCode.FILE_INVALID_EXTENSION, message=str(e))
        raise HTTPException(
            status_code=422,
            detail=err.to_detail() if settings.use_structured_errors else err.message,
        )


@router.put("/upload/chunked/{upload_id}/chunk/{chunk_index}")
async def chunked_upload_chunk(
    upload_id: str,
    chunk_index: int,
    file: UploadFile = File(...),
):
    """
    Upload a single chunk. Idempotent: re-uploading same chunk is safe.
    """
    if not settings.chunk_upload_enabled:
        raise HTTPException(status_code=503, detail="Chunked upload is disabled")

    data = await file.read()
    success, err = await chunked_upload_service.write_chunk(upload_id, chunk_index, data)

    if not success:
        raise HTTPException(
            status_code=400,
            detail=err or "Failed to write chunk",
        )
    return {"chunk": chunk_index, "status": "ok"}


@router.get("/upload/chunked/{upload_id}/status", response_model=ChunkedUploadStatusResponse)
async def chunked_upload_status(upload_id: str):
    """Get upload status. Use for resumable uploads to discover missing chunks."""
    status = await chunked_upload_service.get_status(upload_id)
    if not status:
        raise HTTPException(status_code=404, detail="Upload session not found or expired")
    return ChunkedUploadStatusResponse(**status)


@router.post("/upload/chunked/{upload_id}/complete", response_model=ChunkedUploadCompleteResponse)
async def chunked_upload_complete(upload_id: str):
    """
    Signal that all chunks are uploaded. Triggers merge and RIM audit.
    Returns audit result when done.
    """
    if not settings.chunk_upload_enabled:
        raise HTTPException(status_code=503, detail="Chunked upload is disabled")

    try:
        result = await chunked_upload_service.complete_and_process(upload_id)
        return ChunkedUploadCompleteResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Chunked upload complete failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
