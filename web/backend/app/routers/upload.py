import uuid
from typing import Optional, List
import asyncio

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile

from app.config import get_settings
from app.logging_config import logger
from app.models.common_schemas import (
    FileInfo,
    VerificationStatus,
    KPI,
    ExtendedAuditResult,
    RiskBadge,
    EUAIActCompliance,
    LegalDisclosures,
    LedgerInfo,
    RiskLevel,
)
from app.models.error_schemas import ErrorCode, StructuredError
from app.models.upload_schemas import UploadResponse
from app.services.abuse_protection import (
    check_abuse_protection,
    record_upload,
)
from app.services.rim_wrapper import run_rim_audit
from app.services.file_validation import (
    read_file_streaming,
    validate_file_extension,
    validate_file_size,
    validate_mime_type,
    compute_file_hash,
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

        # ─── Canonical RIM-OS v2 audit (immutable engine) ───────────────────
        # Persist contents to a temporary file and delegate to rim_os_v2 via
        # the canonical wrapper `run_rim_audit`, which enforces Genesis and
        # ledger invariants.
        import os
        import tempfile

        suffix = os.path.splitext(file.filename or "")[1] or ".bin"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(contents)
            tmp_path = tmp.name

        try:
            report = run_rim_audit(tmp_path)
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

        summary = report.get("summary", {}) or {}

        # Minimal KPI/verification shim to preserve response shape.
        audit_score = float(summary.get("integrity_score_0_100", 0.0))
        risk_level = summary.get("risk_level", "HIGH")
        anomaly_fraction = float(summary.get("anomaly_fraction", 0.0))
        kag_score = float(summary.get("avg_kag_separability", 0.0))
        anomaly_count = int(summary.get("anomaly_count", 0))

        coverage_pct = (1.0 - anomaly_fraction) * 100.0

        def adjust_status(base: str) -> str:
            """
            Downgrade KPI visual status when overall RIM-OS risk is elevated.

            - HIGH  → all metrics shown as 'warning'
            - MEDIUM → no metric shown as 'excellent'
            - LOW   → use base status as-is
            """
            if risk_level == "HIGH":
                return "warning"
            if risk_level == "MEDIUM" and base == "excellent":
                return "good"
            return base

        # Legacy-compatible 5 KPI layout, backed by RIM-OS summary, with
        # visual status harmonised to the overall risk_level.
        audit_status = adjust_status(
            "excellent" if audit_score >= 90 else "good" if audit_score >= 70 else "warning"
        )
        issues_status = adjust_status("warning" if anomaly_count > 0 else "excellent")
        kag_status = adjust_status(
            "excellent" if kag_score >= 0.5 else "good" if kag_score >= 0.3 else "warning"
        )
        coverage_status = adjust_status(
            "excellent" if anomaly_fraction == 0.0 else "good" if anomaly_fraction <= 0.05 else "warning"
        )

        mock_kpis = [
            KPI(
                id="kpi-1",
                label="Audit Score",
                value=audit_score,
                trend="stable" if risk_level == "LOW" else "down",
                status=audit_status,
                description="RIM-OS integrity score (0–100)",
            ),
            KPI(
                id="kpi-2",
                label="Issues Found",
                value=anomaly_count,
                trend="up" if anomaly_count > 0 else "down",
                status=issues_status,
                description="Count of anomalous chunks detected by RIM-OS",
            ),
            KPI(
                id="kpi-3",
                label="KAG Score",
                value=f"{kag_score:.4f}",
                trend="up" if kag_score >= 0.5 else "down",
                status=kag_status,
                description="Average KAG separability from RIM-OS",
            ),
            KPI(
                id="kpi-4",
                label="Coverage",
                value=f"{coverage_pct:.1f}%",
                trend="up" if anomaly_fraction <= 0.05 else "down",
                status=coverage_status,
                description="1 − anomaly_fraction, scaled to percentage",
            ),
            KPI(
                id="kpi-5",
                label="Penrose Sector",
                value=0,
                trend="stable",
                status=adjust_status("warning"),
                description="Penrose details are now handled solely inside RIM-OS",
            ),
        ]
        # Map RIM-OS risk_level back to legacy PASS97-style status strings.
        if risk_level == "LOW":
            status_str = "Verified"
        elif risk_level == "MEDIUM":
            status_str = "Verified with Warnings"
        else:
            status_str = "Verification Failed"

        # Use only ASCII characters here to keep PDF generation compatible
        # with the built-in Helvetica font used by fpdf.
        checks = [
            "Stage 1 - Schema & Genesis: OK",
            f"Stage 2 - Entropy: avg_entropy_bits={summary.get('avg_entropy_bits', 0.0):.4f}",
            f"Stage 3 - Penrose geometry: avg_penrose_match={summary.get('avg_penrose_match', 0.0):.4f}",
            f"Stage 4 - Anomalies: anomaly_fraction={anomaly_fraction:.4f}, count={anomaly_count}",
            f"Stage 5 - Risk: risk_level={risk_level}",
        ]

        mock_verification = VerificationStatus(
            status=status_str,
            confidence=int(audit_score),
            timestamp=report.get("time_utc", ""),
            checks=checks,
        )

        # Preserve legacy behavior: fileHash is pure SHA-256 of raw contents.
        file_hash = compute_file_hash(contents)

        # Build a minimal ExtendedAuditResult for report caching.
        failed_checks = 0 if risk_level == "LOW" else 1 if risk_level == "MEDIUM" else 3
        risk_badge = RiskBadge.from_audit_score(audit_score, failed_checks)
        eu_ai_act = EUAIActCompliance.from_risk_badge(risk_badge)
        legal_disclosures = LegalDisclosures.default()

        ledger = report.get("ledger") or {}
        integrity_block = report.get("integrity", {}) or {}
        ledger_info = LedgerInfo(
            ledger_id="RIM-OS-LEDGER",
            sequence_number=0,
            prev_state=ledger.get("prev_state"),
            next_state_hash=ledger.get("next_state_hash"),
            audit_content_sha256=integrity_block.get("audit_content_sha256", file_hash),
            entry_hash=ledger.get("events_hash", file_hash),
        )

        # Penrose parameters from first chunk manifold geometry (unique per audit)
        from app.utils.penrose import extract_penrose_from_report

        penrose_details = extract_penrose_from_report(report, fallback_hash=file_hash)

        extended = ExtendedAuditResult(
            kpis=mock_kpis,
            verification=mock_verification,
            file_hash=file_hash,
            anomalies=[],
            risk_badge=risk_badge,
            eu_ai_act=eu_ai_act,
            legal_disclosures=legal_disclosures,
            ledger=ledger_info,
            penrose_details=penrose_details,
            tile_hash=penrose_details["tile_hash"],
        )

        upload_id = str(uuid.uuid4())

        # Cache for PDF/HTML/SVG report endpoints.
        from app.routers.report import cache_audit_result

        cache_audit_result(upload_id, extended)

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


@router.post("/upload/batch")
async def upload_audit_batch(
    request: Request,
    files: List[UploadFile] = File(...),
):
    """
    Batch upload endpoint for processing multiple audit artifacts in parallel.

    Each file is processed independently via the canonical /api/upload logic.
    """
    if not files:
        raise HTTPException(status_code=422, detail="No files provided")

    if len(files) > settings.max_batch_files:
        raise HTTPException(
            status_code=413,
            detail=f"Too many files in batch. Maximum is {settings.max_batch_files}.",
        )

    async def _process_single(file: UploadFile):
        try:
            # Reuse the existing single-file upload handler for full validation,
            # abuse protection, RIM-OS audit, caching, and response shaping.
            resp: UploadResponse = await upload_audit_file(request, file)
            return {
                "fileName": resp.fileInfo.name,
                "status": "ok",
                "uploadId": resp.uploadId,
                "verification": resp.verification,
                "kpis": resp.kpis,
                "fileHash": resp.fileHash,
            }
        except HTTPException as exc:
            # Preserve structured error detail where available.
            return {
                "fileName": file.filename or "",
                "status": "failed",
                "error": exc.detail,
            }
        except Exception as exc:  # pragma: no cover - defensive
            return {
                "fileName": file.filename or "",
                "status": "failed",
                "error": str(exc),
            }

    tasks = [_process_single(f) for f in files]
    results = await asyncio.gather(*tasks)

    batch_id = str(uuid.uuid4())
    total_size = sum(getattr(f, "spool_max_size", 0) or 0 for f in files)
    if total_size > settings.max_batch_total_size:
        # Soft guard: warn but still return per-file results.
        logger.warning(
            "Batch total size estimate exceeded: size=%s limit=%s",
            total_size,
            settings.max_batch_total_size,
        )

    return {"batchId": batch_id, "results": results}
