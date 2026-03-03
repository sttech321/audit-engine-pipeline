"""
Report generation router.

PASS97 Spec Compliant:
- PDF report download endpoint
- SVG visualization endpoint
- Extended audit results with full output contract

Provides endpoints for generating and downloading audit reports.
"""
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse, Response

from app.logging_config import logger
from app.models.common_schemas import (
    KPI, VerificationStatus, RiskBadge, Anomaly, AnomalyType,
    EUAIActCompliance, LegalDisclosures, LedgerInfo, RiskLevel,
    ExtendedAuditResult
)
from app.services.pdf_generator import get_pdf_generator, generate_pdf_html, PDF_AVAILABLE
from app.services.svg_generator import generate_penrose_svg, generate_minimal_svg
from app.services.ledger_service import get_ledger


router = APIRouter()


# ─── In-Memory Audit Result Cache ────────────────────────────────────────────
# In production, this would be a database or Redis cache
_audit_cache: dict = {}


def cache_audit_result(upload_id: str, result: ExtendedAuditResult) -> None:
    """Cache an audit result for later report generation."""
    _audit_cache[upload_id] = result


def get_cached_audit(upload_id: str) -> Optional[ExtendedAuditResult]:
    """Retrieve a cached audit result."""
    return _audit_cache.get(upload_id)


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


@router.get("/ledger")
async def get_ledger_chain(
    start: int = Query(0, ge=0, description="Start sequence number"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum entries to return")
):
    """
    Get ledger chain entries.
    
    Args:
        start: Starting sequence number
        limit: Maximum number of entries
        
    Returns:
        List of ledger entries
    """
    ledger = get_ledger()
    chain = ledger.export_chain()
    
    return {
        "chain_length": len(chain),
        "entries": chain[start:start + limit],
        "integrity_valid": ledger.verify_chain_integrity()
    }


@router.get("/ledger/{sequence}")
async def get_ledger_entry(sequence: int):
    """
    Get a specific ledger entry by sequence number.
    
    Args:
        sequence: The sequence number
        
    Returns:
        Ledger entry details
    """
    ledger = get_ledger()
    entry = ledger.get_entry(sequence)
    
    if not entry:
        raise HTTPException(
            status_code=404,
            detail=f"Ledger entry not found: sequence {sequence}"
        )
    
    return entry.to_dict()
