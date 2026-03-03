import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile

from app.config import get_settings
from app.logging_config import logger
from app.models.common_schemas import FileInfo
from app.models.error_schemas import ErrorCode, StructuredError
from app.models.upload_schemas import UploadResponse
from app.services.abuse_protection import (
    check_abuse_protection,
    record_upload,
)
from app.services.audit_pipeline import process_audit_artifact, process_audit_artifact_extended
from app.routers.report import cache_audit_result
from app.services.file_validation import (
    read_file_streaming,
    validate_file_extension,
    validate_file_size,
    validate_mime_type,
)
from app.services.metadata_parser import parse_metadata, validate_metadata
from app.services.signature_verification import verify_artifact_signature

router = APIRouter()
settings = get_settings()


def raise_structured_error(
    error: StructuredError,
    status_code: int = 422
) -> None:
    """
    Raise HTTPException with structured error.
    
    Maintains backward compatibility by using the message as detail,
    while adding structured error info when enabled.
    """
    if settings.use_structured_errors:
        raise HTTPException(
            status_code=status_code,
            detail=error.to_detail()
        )
    else:
        # Legacy format - just the message
        raise HTTPException(
            status_code=status_code,
            detail=error.message
        )


@router.post("/upload", response_model=UploadResponse)
async def upload_audit_file(
    request: Request,
    file: UploadFile = File(...)
):
    """
    Upload and process an audit artifact file.
    
    This endpoint supports .lm3z, .rim0, and .rim95 artifact formats.
    
    New additive features (all backward compatible):
    - File extension validation
    - MIME type validation  
    - Metadata parsing with structured extraction
    - Ed25519 signature verification
    - Rate limiting and abuse protection
    - Structured error responses
    """
    try:
        # ─── Stage 0a: Extension Validation (Additive) ───────────────────────
        if settings.validate_file_extension:
            ext_valid, ext_error = validate_file_extension(file.filename or "")
            if not ext_valid:
                logger.warning(f"Rejected invalid extension: {file.filename}")
                raise_structured_error(ext_error, status_code=422)
        
        # ─── Stage 0b: MIME Type Validation (Additive) ───────────────────────
        if settings.validate_mime_type:
            mime_valid, mime_error = validate_mime_type(file.content_type)
            if not mime_valid:
                logger.warning(f"Rejected invalid MIME type: {file.content_type}")
                raise_structured_error(mime_error, status_code=422)
        
        # ─── Read File Contents (Streaming) ──────────────────────────────────
        # Use streaming read to avoid loading entire file into memory at once
        # This is memory-safe for large files (spools to disk if needed)
        read_result = await read_file_streaming(file, max_size=settings.max_file_size)
        
        if not read_result.valid:
            logger.warning(f"File read failed: {read_result.error.message if read_result.error else 'unknown'}")
            if read_result.error:
                raise_structured_error(read_result.error, status_code=413 if read_result.error.code == ErrorCode.FILE_TOO_LARGE else 422)
            else:
                raise HTTPException(status_code=500, detail="Failed to read file")
        
        contents = read_result.contents
        file_size = read_result.file_size

        logger.info(f"Received file: {file.filename} ({file_size} bytes)")

        # ─── Stage 1: Size Validation (Preserves Existing Behavior) ──────────
        # Stage 1 — Ingestion guard: reject empty file at API level
        if file_size == 0:
            logger.warning(f"Rejected empty file: {file.filename}")
            if settings.use_structured_errors:
                raise_structured_error(
                    StructuredError(
                        code=ErrorCode.FILE_EMPTY,
                        message="File is empty. Upload a valid audit artifact."
                    ),
                    status_code=422
                )
            else:
                raise HTTPException(status_code=422, detail="File is empty. Upload a valid audit artifact.")

        # Check max file size
        if file_size > settings.max_file_size:
            logger.warning(f"Rejected oversized file: {file.filename} ({file_size} bytes)")
            if settings.use_structured_errors:
                raise_structured_error(
                    StructuredError(
                        code=ErrorCode.FILE_TOO_LARGE,
                        message=f"File too large. Maximum size is {settings.max_file_size // 1_000_000}MB."
                    ),
                    status_code=413
                )
            else:
                raise HTTPException(
                    status_code=413,
                    detail=f"File too large. Maximum size is {settings.max_file_size // 1_000_000}MB."
                )

        # ─── Stage 0c: Abuse Protection (Additive) ───────────────────────────
        if settings.enable_deduplication or settings.enable_replay_detection:
            passed, abuse_error = check_abuse_protection(
                contents=contents,
                request=request,
                enable_dedup=settings.enable_deduplication,
                enable_replay=settings.enable_replay_detection
            )
            if not passed:
                logger.warning(f"Abuse protection triggered for {file.filename}")
                raise_structured_error(abuse_error, status_code=429)

        # ─── Stage 0d: Metadata Parsing (Additive) ───────────────────────────
        metadata_result = None
        signature_result = None
        
        if settings.parse_metadata:
            # Use strict parsing based on config (default: strict)
            metadata_result = parse_metadata(
                contents, 
                file.filename, 
                strict=settings.strict_metadata_parsing
            )
            
            if not metadata_result.success:
                logger.warning(f"Metadata parsing failed for {file.filename}: {metadata_result.error_message}")
                if settings.require_valid_metadata:
                    raise_structured_error(
                        StructuredError(
                            code=ErrorCode.METADATA_PARSE_ERROR,
                            message=metadata_result.error_message or "Failed to parse artifact metadata"
                        ),
                        status_code=422
                    )
            else:
                # Validate metadata completeness
                meta_valid, meta_error = validate_metadata(metadata_result.metadata)
                if not meta_valid and settings.require_valid_metadata:
                    raise_structured_error(
                        StructuredError(
                            code=ErrorCode.METADATA_INVALID_FORMAT,
                            message=meta_error or "Invalid artifact metadata"
                        ),
                        status_code=422
                    )

        # ─── Stage 0e: Signature Verification (Additive) ─────────────────────
        if settings.verify_signatures and metadata_result and metadata_result.success:
            metadata = metadata_result.metadata
            
            if metadata.public_key and metadata.signature:
                signature_result = verify_artifact_signature(
                    contents=contents,
                    metadata_signature=metadata.signature,
                    metadata_public_key=metadata.public_key,
                    payload=metadata_result.raw_payload
                )
                
                if not signature_result.verified:
                    logger.warning(
                        f"Signature verification failed for {file.filename}: "
                        f"{signature_result.error_code}"
                    )
                    if settings.require_valid_signature:
                        raise_structured_error(
                            StructuredError(
                                code=ErrorCode.SIGNATURE_VERIFICATION_FAILED,
                                message=signature_result.error_message or "Signature verification failed"
                            ),
                            status_code=422
                        )
                else:
                    logger.info(f"Signature verified for {file.filename}")

        # ─── PASS97 Pipeline (Unchanged - Existing Logic) ───────────────────
        # PASS97 pipeline integration (deterministic processing)
        mock_kpis, mock_verification, file_hash = process_audit_artifact(contents, file.filename)
        
        # Generate extended result for report generation (additive)
        extended_result, _ = process_audit_artifact_extended(contents, file.filename)

        upload_id = str(uuid.uuid4())
        
        # Cache extended result for PDF/SVG report generation
        cache_audit_result(upload_id, extended_result)
        
        # Extract the dynamic score and status to inject into the NFT metadata
        dynamic_score = next((kpi.value for kpi in mock_kpis if kpi.label == "Audit Score"), 0)
        dynamic_status = mock_verification.status

        logger.info(f"Processed {file.filename}: score={dynamic_score}, status={dynamic_status}")

        # Record successful upload for deduplication
        if settings.enable_deduplication:
            record_upload(contents)

        # ─── Build Response (Unchanged Schema) ───────────────────────────────
        response_metadata = {
            "name": f"Audit Report: {file.filename}",
            "description": "Cryptographic audit artifact verified by Pass97 pipeline.",
            "attributes": [
                {"trait_type": "Audit Score", "value": dynamic_score},
                {"trait_type": "Status", "value": dynamic_status}
            ]
        }
        
        # Add signature verification result if available
        if signature_result:
            response_metadata["signature_verified"] = signature_result.verified
            if signature_result.public_key_hex:
                response_metadata["public_key"] = signature_result.public_key_hex[:16] + "..."
        
        # Add parsed metadata info if available
        if metadata_result and metadata_result.success and metadata_result.metadata:
            meta = metadata_result.metadata
            response_metadata["artifact_format"] = meta.format_type.value
            response_metadata["artifact_version"] = meta.version
            if meta.artifact_id:
                response_metadata["artifact_id"] = meta.artifact_id

        return UploadResponse(
            fileInfo=FileInfo(name=file.filename, size=file_size, type=file.content_type or "application/octet-stream"),
            kpis=mock_kpis,
            verification=mock_verification,
            fileHash=file_hash,
            uploadId=upload_id,
            metadata=response_metadata
        )
    except HTTPException:
        raise  # Re-raise HTTPException as-is
    except Exception as e:
        logger.error(f"Failed to process file {file.filename}: {e}")
        
        # Prevent internal error leakage
        if settings.hide_internal_errors:
            error_message = "An unexpected error occurred while processing the file."
        else:
            error_message = f"Failed to process file: {str(e)}"
        
        if settings.use_structured_errors:
            raise HTTPException(
                status_code=500,
                detail={
                    "error": {
                        "code": ErrorCode.INTERNAL_ERROR.value,
                        "message": error_message,
                        "details": {} if settings.hide_internal_errors else {"exception": str(e)}
                    }
                }
            )
        else:
            raise HTTPException(status_code=500, detail=error_message)
