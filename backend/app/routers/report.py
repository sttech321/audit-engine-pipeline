"""
Report generation router.

PASS97 Spec Compliant:
- PDF report download endpoint
- SVG visualization endpoint
- Extended audit results with full output contract

Provides endpoints for generating and downloading audit reports.
"""
import json
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse, Response

from app.config import get_settings
from app.logging_config import logger
from app.models.common_schemas import (
    KPI, VerificationStatus, RiskBadge, Anomaly, AnomalyType,
    EUAIActCompliance, LegalDisclosures, LedgerInfo, RiskLevel,
    ExtendedAuditResult
)
from app.services.pdf_generator import get_pdf_generator, generate_pdf_html, PDF_AVAILABLE
from app.services.svg_generator import generate_penrose_svg, generate_minimal_svg


router = APIRouter()


# ─── In-Memory Audit Result Cache ────────────────────────────────────────────
# In production, this would be a database or Redis cache
_audit_cache: dict = {}


def _report_cache_dir() -> Path:
    """Resolve the persistent cache directory for audit reports."""
    settings = get_settings()
    path = Path(settings.report_cache_dir)
    if not path.is_absolute():
        path = Path(__file__).resolve().parents[2] / path
    path.mkdir(parents=True, exist_ok=True)
    return path


def _report_cache_path(upload_id: str) -> Path:
    """Get the on-disk cache file for a report."""
    return _report_cache_dir() / f"{upload_id}.json"


def _write_audit_to_disk(upload_id: str, result: ExtendedAuditResult) -> None:
    """Persist an audit result so report URLs survive process restarts."""
    cache_path = _report_cache_path(upload_id)
    cache_path.write_text(
        json.dumps(result.model_dump(mode="json"), indent=2),
        encoding="utf-8",
    )


def _read_audit_from_disk(upload_id: str) -> Optional[ExtendedAuditResult]:
    """Load a persisted audit result if it exists."""
    cache_path = _report_cache_path(upload_id)
    if not cache_path.exists():
        return None

    try:
        return ExtendedAuditResult.model_validate_json(
            cache_path.read_text(encoding="utf-8")
        )
    except Exception as exc:
        logger.warning(
            "Failed to load cached audit result for %s from %s: %s",
            upload_id,
            cache_path,
            exc,
        )
        return None


def cache_audit_result(upload_id: str, result: ExtendedAuditResult) -> None:
    """Cache an audit result for later report generation."""
    _audit_cache[upload_id] = result
    try:
        _write_audit_to_disk(upload_id, result)
    except Exception as exc:
        logger.warning(
            "Failed to persist audit result for %s: %s",
            upload_id,
            exc,
        )


def get_cached_audit(upload_id: str) -> Optional[ExtendedAuditResult]:
    """Retrieve a cached audit result."""
    cached = _audit_cache.get(upload_id)
    if cached is not None:
        return cached

    cached = _read_audit_from_disk(upload_id)
    if cached is not None:
        _audit_cache[upload_id] = cached
    return cached


# ─── Report Endpoints ────────────────────────────────────────────────────────

@router.get("/report/{upload_id}/pdf")
async def download_pdf_report(upload_id: str):
    """
    Download PDF audit report.
    
    Args:
        upload_id: The upload ID from the audit response
        
    Returns:
        PDF file as download
    """
    cached = get_cached_audit(upload_id)
    if not cached:
        raise HTTPException(
            status_code=404,
            detail=f"Audit result not found for upload ID: {upload_id}"
        )
    
    try:
        # Generate SVG
        penrose_svg = None
        if cached.penrose_details:
            penrose_svg = generate_penrose_svg(
                cached.penrose_details,
                risk_level=cached.risk_badge.level.value
            )
        
        # Generate PDF
        generator = get_pdf_generator()
        pdf_bytes = generator.generate_report(
            kpis=cached.kpis,
            verification=cached.verification,
            file_hash=cached.file_hash,
            anomalies=cached.anomalies,
            risk_badge=cached.risk_badge,
            eu_ai_act=cached.eu_ai_act,
            legal_disclosures=cached.legal_disclosures,
            ledger=cached.ledger,
            penrose_svg=penrose_svg,
            filename=f"audit_{upload_id}",
            tile_hash=cached.tile_hash,
            cache_key=upload_id
        )
        
        # Return PDF (fpdf2 always works - pure Python)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="pass97_report_{upload_id}.pdf"'
            }
        )
    except Exception as e:
        logger.error(f"PDF generation failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate PDF report")


@router.get("/report/{upload_id}/html", response_class=HTMLResponse)
async def view_html_report(upload_id: str):
    """
    View HTML audit report in browser.
    
    Args:
        upload_id: The upload ID from the audit response
        
    Returns:
        HTML report page
    """
    cached = get_cached_audit(upload_id)
    if not cached:
        raise HTTPException(
            status_code=404,
            detail=f"Audit result not found for upload ID: {upload_id}"
        )
    
    try:
        # Generate SVG
        penrose_svg = None
        if cached.penrose_details:
            penrose_svg = generate_penrose_svg(
                cached.penrose_details,
                risk_level=cached.risk_badge.level.value
            )
        
        # Generate HTML
        html_content = generate_pdf_html(
            kpis=cached.kpis,
            verification=cached.verification,
            file_hash=cached.file_hash,
            anomalies=cached.anomalies,
            risk_badge=cached.risk_badge,
            eu_ai_act=cached.eu_ai_act,
            legal_disclosures=cached.legal_disclosures,
            ledger=cached.ledger,
            penrose_svg=penrose_svg,
            filename=f"audit_{upload_id}",
            tile_hash=cached.tile_hash
        )
        
        return HTMLResponse(content=html_content)
    except Exception as e:
        logger.error(f"HTML report generation failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate HTML report")


@router.get("/report/{upload_id}/svg")
async def get_penrose_svg(
    upload_id: str,
    minimal: bool = Query(False, description="Return minimal icon version")
):
    """
    Get SVG Penrose visualization.
    
    Args:
        upload_id: The upload ID from the audit response
        minimal: If True, return a small icon version
        
    Returns:
        SVG image
    """
    cached = get_cached_audit(upload_id)
    if not cached:
        raise HTTPException(
            status_code=404,
            detail=f"Audit result not found for upload ID: {upload_id}"
        )
    
    try:
        if minimal:
            sector = cached.penrose_details.get("sector", 0) if cached.penrose_details else 0
            svg_content = generate_minimal_svg(
                sector=sector,
                risk_level=cached.risk_badge.level.value
            )
        else:
            if not cached.penrose_details:
                raise HTTPException(status_code=404, detail="Penrose details not available")
            
            svg_content = generate_penrose_svg(
                cached.penrose_details,
                risk_level=cached.risk_badge.level.value
            )
        
        return Response(
            content=svg_content,
            media_type="image/svg+xml"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"SVG generation failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate SVG")


@router.get("/report/{upload_id}/extended")
async def get_extended_result(upload_id: str):
    """
    Get the full extended audit result with all PASS97 fields.
    
    Args:
        upload_id: The upload ID from the audit response
        
    Returns:
        ExtendedAuditResult JSON
    """
    cached = get_cached_audit(upload_id)
    if not cached:
        raise HTTPException(
            status_code=404,
            detail=f"Audit result not found for upload ID: {upload_id}"
        )
    
    return cached


@router.get("/report/{upload_id}")
async def get_report_result(upload_id: str):
    """
    Get the cached audit result JSON including map_position coordinates.
    """
    cached = get_cached_audit(upload_id)
    if not cached:
        raise HTTPException(
            status_code=404,
            detail=f"Audit result not found for upload ID: {upload_id}"
        )
    return cached


@router.get("/ledger")
async def get_ledger_chain(
    start: int = Query(0, ge=0, description="Start sequence number"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum entries to return")
):
    """
    Ledger endpoint is disabled under canonical RIM-OS integration.
    
    All authoritative ledger information now lives solely inside the
    RIM-OS v2 engine and is exposed per-audit via ExtendedAuditResult.ledger.
    """
    raise HTTPException(status_code=410, detail="Ledger API is deprecated under RIM-OS v2.")


@router.get("/ledger/{sequence}")
async def get_ledger_entry(sequence: int):
    """
    Ledger entry endpoint is disabled under canonical RIM-OS integration.
    """
    raise HTTPException(status_code=410, detail="Ledger API is deprecated under RIM-OS v2.")
