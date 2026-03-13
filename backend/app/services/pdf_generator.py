"""
PDF report generation service for PASS97 audits.

PASS97 Spec Compliant:
- Server-side PDF generation from JSON + SVG
- Downloadable audit report
- Includes all pipeline stages, KPIs, risk assessment

Uses fpdf2 for pure-Python PDF generation (no native dependencies).
"""
import base64
import html
import time
from typing import Dict, Any, List, Optional
from datetime import datetime
from io import BytesIO

from fpdf import FPDF

from app.models.common_schemas import (
    KPI, VerificationStatus, RiskBadge, Anomaly, 
    EUAIActCompliance, LegalDisclosures, LedgerInfo
)

# fpdf2 is always available (pure Python)
PDF_AVAILABLE = True


# ─── PDF Template Constants ──────────────────────────────────────────────────

PDF_STYLES = """
<style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { 
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        line-height: 1.6;
        color: #1e293b;
        background: #fff;
        padding: 40px;
        max-width: 800px;
        margin: 0 auto;
    }
    .header {
        text-align: center;
        border-bottom: 3px solid #3b82f6;
        padding-bottom: 20px;
        margin-bottom: 30px;
    }
    .header h1 {
        color: #0f172a;
        font-size: 28px;
        margin-bottom: 5px;
    }
    .header .subtitle {
        color: #64748b;
        font-size: 14px;
    }
    .section {
        margin-bottom: 30px;
        page-break-inside: avoid;
    }
    .section-title {
        font-size: 18px;
        color: #1e40af;
        border-bottom: 1px solid #e2e8f0;
        padding-bottom: 8px;
        margin-bottom: 15px;
    }
    .risk-badge {
        display: inline-block;
        padding: 8px 16px;
        border-radius: 20px;
        color: white;
        font-weight: bold;
        font-size: 14px;
    }
    .risk-LOW { background: #22c55e; }
    .risk-MEDIUM { background: #eab308; }
    .risk-HIGH { background: #f97316; }
    .risk-CRITICAL { background: #ef4444; }
    .kpi-grid {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 15px;
    }
    .kpi-card {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 15px;
    }
    .kpi-label {
        font-size: 12px;
        color: #64748b;
        text-transform: uppercase;
    }
    .kpi-value {
        font-size: 24px;
        font-weight: bold;
        color: #0f172a;
    }
    .kpi-status {
        font-size: 11px;
        padding: 2px 8px;
        border-radius: 10px;
        display: inline-block;
    }
    .status-excellent { background: #dcfce7; color: #166534; }
    .status-good { background: #fef3c7; color: #92400e; }
    .status-warning { background: #fee2e2; color: #991b1b; }
    .verification-status {
        text-align: center;
        padding: 20px;
        background: #f0f9ff;
        border-radius: 8px;
        margin-bottom: 20px;
    }
    .verification-status h3 {
        color: #0369a1;
        font-size: 20px;
    }
    .checks-list {
        list-style: none;
        padding: 0;
    }
    .checks-list li {
        padding: 8px 0;
        border-bottom: 1px solid #e2e8f0;
        font-size: 14px;
    }
    .checks-list li:last-child { border-bottom: none; }
    .check-pass { color: #16a34a; }
    .check-fail { color: #dc2626; }
    .anomaly-item {
        background: #fef2f2;
        border-left: 4px solid #ef4444;
        padding: 10px 15px;
        margin-bottom: 10px;
        border-radius: 0 4px 4px 0;
    }
    .anomaly-type {
        font-weight: bold;
        color: #991b1b;
    }
    .eu-ai-table {
        width: 100%;
        border-collapse: collapse;
        margin-top: 10px;
    }
    .eu-ai-table th, .eu-ai-table td {
        border: 1px solid #e2e8f0;
        padding: 10px;
        text-align: left;
    }
    .eu-ai-table th {
        background: #f1f5f9;
        color: #334155;
    }
    .legal-section {
        background: #fffbeb;
        border: 1px solid #fcd34d;
        border-radius: 8px;
        padding: 20px;
        font-size: 12px;
    }
    .legal-section h4 {
        color: #92400e;
        margin-bottom: 10px;
    }
    .legal-section ul {
        margin-left: 20px;
        color: #78350f;
    }
    .hash-display {
        font-family: 'Courier New', monospace;
        font-size: 11px;
        background: #f1f5f9;
        padding: 8px;
        border-radius: 4px;
        word-break: break-all;
    }
    .penrose-svg {
        text-align: center;
        margin: 20px 0;
    }
    .footer {
        margin-top: 40px;
        padding-top: 20px;
        border-top: 1px solid #e2e8f0;
        text-align: center;
        font-size: 11px;
        color: #94a3b8;
    }
    .footer-note {
        margin-top: 8px;
        font-size: 10px;
        color: #94a3b8;
    }
</style>
"""


def _format_timestamp(ts: str) -> str:
    """Format Unix timestamp to human-readable date."""
    try:
        unix_ts = float(ts)
        dt = datetime.fromtimestamp(unix_ts)
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except:
        return ts


def _escape(text: str) -> str:
    """HTML escape text."""
    return html.escape(str(text))


def generate_pdf_html(
    kpis: List[KPI],
    verification: VerificationStatus,
    file_hash: str,
    anomalies: List[Anomaly],
    risk_badge: RiskBadge,
    eu_ai_act: EUAIActCompliance,
    legal_disclosures: LegalDisclosures,
    ledger: Optional[LedgerInfo] = None,
    penrose_svg: Optional[str] = None,
    filename: str = "audit_artifact",
    tile_hash: Optional[str] = None
) -> str:
    """
    Generate HTML content for PDF report.
    
    This HTML can be converted to PDF using a headless browser or PDF library.
    
    Args:
        kpis: List of KPI results
        verification: Verification status
        file_hash: SHA-256 of audited file
        anomalies: List of detected anomalies
        risk_badge: Risk assessment badge
        eu_ai_act: EU AI Act compliance info
        legal_disclosures: Legal scope disclosures
        ledger: Optional ledger chain info
        penrose_svg: Optional SVG visualization
        filename: Original filename
        tile_hash: Optional tile hash for NFT
        
    Returns:
        Complete HTML document string
    """
    # Build HTML document
    html_parts = [
        '<!DOCTYPE html>',
        '<html lang="en">',
        '<head>',
        '  <meta charset="UTF-8">',
        '  <meta name="viewport" content="width=device-width, initial-scale=1.0">',
        f'  <title>PASS97 Audit Report - {_escape(filename)}</title>',
        PDF_STYLES,
        '</head>',
        '<body>',
    ]
    
    # Header
    html_parts.append(f'''
    <div class="header">
        <h1>PASS97 Audit Report</h1>
        <p class="subtitle">Cryptographic Model Weight Audit</p>
        <p class="subtitle">{_escape(filename)} | {_format_timestamp(verification.timestamp)}</p>
    </div>
    ''')
    
    # Risk Badge and Verification Summary
    html_parts.append(f'''
    <div class="section">
        <div class="verification-status">
            <span class="risk-badge risk-{risk_badge.level.value}">{risk_badge.label}</span>
            <h3 style="margin-top: 15px;">{_escape(verification.status)}</h3>
            <p>Confidence: {verification.confidence}%</p>
        </div>
    </div>
    ''')
    
    # KPIs
    html_parts.append('<div class="section">')
    html_parts.append('<h2 class="section-title">Key Performance Indicators</h2>')
    html_parts.append('<div class="kpi-grid">')
    for kpi in kpis:
        status_class = f"status-{kpi.status}"
        html_parts.append(f'''
        <div class="kpi-card">
            <div class="kpi-label">{_escape(kpi.label)}</div>
            <div class="kpi-value">{_escape(str(kpi.value))}</div>
            <span class="kpi-status {status_class}">{_escape(kpi.status.upper())}</span>
            <p style="font-size: 11px; color: #64748b; margin-top: 5px;">{_escape(kpi.description or '')}</p>
        </div>
        ''')
    html_parts.append('</div></div>')
    
    # Verification Checks
    html_parts.append('<div class="section">')
    html_parts.append('<h2 class="section-title">Pipeline Verification Checks</h2>')
    html_parts.append('<ul class="checks-list">')
    for check in verification.checks:
        is_fail = "FAILED" in check
        check_class = "check-fail" if is_fail else "check-pass"
        icon = "✗" if is_fail else "✓"
        html_parts.append(f'<li class="{check_class}">{icon} {_escape(check)}</li>')
    html_parts.append('</ul></div>')
    
    # Anomalies
    if anomalies:
        html_parts.append('<div class="section">')
        html_parts.append('<h2 class="section-title">Detected Anomalies</h2>')
        for anomaly in anomalies:
            html_parts.append(f'''
            <div class="anomaly-item">
                <span class="anomaly-type">[{anomaly.severity.value}] {anomaly.anomaly_type.value}</span>
                <p>{_escape(anomaly.message)}</p>
                <small>Stage: {_escape(anomaly.stage)}</small>
            </div>
            ''')
        html_parts.append('</div>')
    
    # Penrose Visualization
    if penrose_svg:
        html_parts.append('<div class="section">')
        html_parts.append('<h2 class="section-title">Penrose P3 Visualization</h2>')
        html_parts.append(f'<div class="penrose-svg">{penrose_svg}</div>')
        html_parts.append('</div>')
    
    # Cryptographic Hashes
    html_parts.append('<div class="section">')
    html_parts.append('<h2 class="section-title">Cryptographic Fingerprints</h2>')
    html_parts.append(f'<p><strong>File Hash (SHA-256):</strong></p>')
    html_parts.append(f'<div class="hash-display">{_escape(file_hash)}</div>')
    if tile_hash:
        html_parts.append(f'<p style="margin-top: 10px;"><strong>Tile Hash:</strong></p>')
        html_parts.append(f'<div class="hash-display">{_escape(tile_hash)}</div>')
    if ledger:
        html_parts.append(f'<p style="margin-top: 10px;"><strong>Ledger Entry:</strong></p>')
        html_parts.append(f'<div class="hash-display">ID: {_escape(ledger.ledger_id)}<br>')
        html_parts.append(f'Sequence: {ledger.sequence_number}<br>')
        html_parts.append(f'Entry Hash: {_escape(ledger.entry_hash)}</div>')
    html_parts.append('</div>')
    
    # EU AI Act Compliance
    html_parts.append('<div class="section">')
    html_parts.append('<h2 class="section-title">EU AI Act Assessment</h2>')
    html_parts.append('<table class="eu-ai-table">')
    html_parts.append(f'''
        <tr><th>Category</th><td>{_escape(eu_ai_act.category.value)}</td></tr>
        <tr><th>Article Reference</th><td>{_escape(eu_ai_act.article_reference)}</td></tr>
        <tr><th>Assessment</th><td>{_escape(eu_ai_act.assessment)}</td></tr>
    ''')
    html_parts.append('<tr><th>Requirements</th><td><ul>')
    for req in eu_ai_act.requirements:
        html_parts.append(f'<li>{_escape(req)}</li>')
    html_parts.append('</ul></td></tr>')
    html_parts.append('</table>')
    html_parts.append(f'<p style="font-size: 11px; color: #92400e; margin-top: 10px;"><em>{_escape(eu_ai_act.disclaimer)}</em></p>')
    html_parts.append('</div>')
    
    # Legal Disclosures
    html_parts.append('<div class="section">')
    html_parts.append('<div class="legal-section">')
    html_parts.append('<h4>Legal Scope Disclosures</h4>')
    html_parts.append(f'<p><strong>Scope:</strong> {_escape(legal_disclosures.weight_space_scope)}</p>')
    html_parts.append('<p style="margin-top: 10px;"><strong>Out of Scope:</strong></p>')
    html_parts.append('<ul>')
    for item in legal_disclosures.out_of_scope:
        html_parts.append(f'<li>{_escape(item)}</li>')
    html_parts.append('</ul>')
    html_parts.append(f'<p style="margin-top: 10px;"><strong>Version:</strong> {_escape(legal_disclosures.version)}</p>')
    if legal_disclosures.notified_body:
        html_parts.append(f'<p><strong>Notified Body:</strong> {_escape(legal_disclosures.notified_body)}</p>')
    html_parts.append('</div></div>')
    
    # Footer
    html_parts.append(f'''
    <div class="footer">
        <p>Generated by PASS97 Audit Pipeline | {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
        <p>This report is for informational purposes only.</p>
    </div>
    ''')
    
    html_parts.append('</body></html>')
    
    return '\n'.join(html_parts)


def generate_pdf_bytes(html_content: str) -> bytes:
    """
    Convert HTML to PDF bytes.
    
    Note: This is a fallback that returns HTML. Use generate_fpdf_report for real PDF.
    
    Args:
        html_content: HTML string to convert
        
    Returns:
        HTML bytes (for browser viewing)
    """
    return html_content.encode('utf-8')


class PASS97PDF(FPDF):
    """Custom FPDF class for PASS97 reports."""
    
    def __init__(self):
        super().__init__()
        self.set_auto_page_break(auto=True, margin=15)
    
    def header(self):
        self.set_font('Helvetica', 'B', 16)
        self.cell(0, 10, 'PASS97 Audit Report', align='C', new_x='LMARGIN', new_y='NEXT')
        self.set_font('Helvetica', '', 10)
        self.set_text_color(100, 100, 100)
        self.cell(0, 6, 'Cryptographic Model Weight Audit', align='C', new_x='LMARGIN', new_y='NEXT')
        self.set_text_color(0, 0, 0)
        self.ln(5)
        # Line separator
        self.set_draw_color(59, 130, 246)
        self.set_line_width(0.5)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(10)
    
    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f'Generated by PASS97 | Page {self.page_no()}', align='C')
    
    def section_title(self, title: str):
        self.set_font('Helvetica', 'B', 12)
        self.set_text_color(30, 64, 175)
        self.cell(0, 8, title, new_x='LMARGIN', new_y='NEXT')
        self.set_draw_color(226, 232, 240)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(3)
        self.set_text_color(0, 0, 0)
    
    def risk_badge(self, level: str, label: str):
        colors = {
            'LOW': (34, 197, 94),
            'MEDIUM': (234, 179, 8),
            'HIGH': (249, 115, 22),
            'CRITICAL': (239, 68, 68),
        }
        level_str = str(level)
        label_str = str(label)
        r, g, b = colors.get(level_str, (100, 100, 100))
        
        self.set_fill_color(r, g, b)
        self.set_text_color(255, 255, 255)
        self.set_font('Helvetica', 'B', 11)
        
        badge_width = self.get_string_width(label_str) + 16
        x = (210 - badge_width) / 2
        self.set_x(x)
        self.cell(badge_width, 8, label_str, fill=True, align='C', new_x='LMARGIN', new_y='NEXT')
        self.set_text_color(0, 0, 0)
        self.ln(3)
    
    def kpi_box(self, label: str, value: str, status: str, description: str = ""):
        # Box background
        x, y = self.get_x(), self.get_y()
        self.set_fill_color(248, 250, 252)
        self.rect(x, y, 90, 25, 'F')
        
        # Label
        self.set_xy(x + 3, y + 2)
        self.set_font('Helvetica', '', 8)
        self.set_text_color(100, 116, 139)
        self.cell(84, 4, str(label).upper(), new_x='LMARGIN', new_y='NEXT')
        
        # Value
        self.set_xy(x + 3, y + 7)
        self.set_font('Helvetica', 'B', 16)
        status_colors = {
            'excellent': (22, 163, 74),
            'good': (59, 130, 246),
            'warning': (234, 179, 8),
        }
        r, g, b = status_colors.get(str(status), (0, 0, 0))
        self.set_text_color(r, g, b)
        self.cell(84, 8, str(value), new_x='LMARGIN', new_y='NEXT')
        
        # Status badge
        self.set_xy(x + 3, y + 16)
        self.set_font('Helvetica', '', 7)
        self.set_text_color(r, g, b)
        self.cell(84, 4, str(status).upper(), new_x='LMARGIN', new_y='NEXT')
        
        self.set_text_color(0, 0, 0)
        return 27  # Height used


def generate_fpdf_report(
    kpis: List[KPI],
    verification: VerificationStatus,
    file_hash: str,
    anomalies: List[Anomaly],
    risk_badge: RiskBadge,
    eu_ai_act: EUAIActCompliance,
    legal_disclosures: LegalDisclosures,
    ledger: Optional[LedgerInfo] = None,
    filename: str = "audit_artifact",
    tile_hash: Optional[str] = None
) -> bytes:
    """
    Generate PDF report using fpdf2.
    
    Args:
        kpis: KPI results
        verification: Verification status
        file_hash: File hash
        anomalies: Detected anomalies
        risk_badge: Risk assessment
        eu_ai_act: EU AI Act info
        legal_disclosures: Legal disclosures
        ledger: Ledger info
        filename: Original filename
        tile_hash: Tile hash
        
    Returns:
        PDF bytes
    """
    pdf = PASS97PDF()
    pdf.add_page()
    
    # Filename and timestamp
    pdf.set_font('Helvetica', '', 9)
    pdf.set_text_color(100, 100, 100)
    ts = _format_timestamp(verification.timestamp)
    pdf.cell(0, 5, f'{filename} | {ts}', align='C', new_x='LMARGIN', new_y='NEXT')
    pdf.set_text_color(0, 0, 0)
    pdf.ln(5)
    
    # Risk Badge
    pdf.risk_badge(risk_badge.level.value, risk_badge.label)
    pdf.ln(3)
    
    # Verification Status
    pdf.set_font('Helvetica', 'B', 14)
    pdf.set_text_color(3, 105, 161)
    pdf.cell(0, 8, str(verification.status), align='C', new_x='LMARGIN', new_y='NEXT')
    pdf.set_font('Helvetica', '', 10)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 6, f'Confidence: {verification.confidence}%', align='C', new_x='LMARGIN', new_y='NEXT')
    pdf.ln(8)
    
    # KPIs Section
    pdf.section_title('Key Performance Indicators')
    pdf.ln(2)
    
    # KPI Grid (2 columns)
    start_y = pdf.get_y()
    col_width = 95
    for i, kpi in enumerate(kpis):
        col = i % 2
        row = i // 2
        x = 10 + col * col_width
        y = start_y + row * 30
        
        if y > 250:  # New page if needed
            pdf.add_page()
            y = pdf.get_y()
            start_y = y
        
        pdf.set_xy(x, y)
        pdf.kpi_box(kpi.label, str(kpi.value), kpi.status, kpi.description or "")
    
    # Move past KPI grid
    rows_needed = (len(kpis) + 1) // 2
    pdf.set_y(start_y + rows_needed * 30 + 5)
    
    # Pipeline Checks
    pdf.section_title('Pipeline Verification Checks')
    pdf.set_font('Helvetica', '', 10)
    for check in verification.checks:
        check_str = str(check)
        is_fail = "FAILED" in check_str
        if is_fail:
            pdf.set_text_color(220, 38, 38)
            icon = "[X]"
        else:
            pdf.set_text_color(22, 163, 74)
            icon = "[OK]"
        pdf.cell(0, 6, f'{icon} {check_str}', new_x='LMARGIN', new_y='NEXT')
    pdf.set_text_color(0, 0, 0)
    pdf.ln(5)
    
    # Anomalies (if any)
    if anomalies:
        pdf.section_title('Detected Anomalies')
        pdf.set_font('Helvetica', '', 9)
        for anomaly in anomalies:
            pdf.set_text_color(153, 27, 27)
            pdf.cell(0, 5, f'[{str(anomaly.severity.value)}] {str(anomaly.anomaly_type.value)}', new_x='LMARGIN', new_y='NEXT')
            pdf.set_text_color(0, 0, 0)
            pdf.cell(0, 5, str(anomaly.message), new_x='LMARGIN', new_y='NEXT')
            pdf.ln(2)
    
    # File Hash
    pdf.section_title('Cryptographic Fingerprints')
    pdf.set_font('Helvetica', 'B', 9)
    pdf.cell(0, 5, 'File Hash (SHA-256):', new_x='LMARGIN', new_y='NEXT')
    pdf.set_font('Courier', '', 8)
    pdf.set_fill_color(241, 245, 249)
    pdf.multi_cell(0, 5, str(file_hash), fill=True)
    
    if tile_hash:
        pdf.ln(2)
        pdf.set_font('Helvetica', 'B', 9)
        pdf.cell(0, 5, 'Tile Hash:', new_x='LMARGIN', new_y='NEXT')
        pdf.set_font('Courier', '', 8)
        pdf.multi_cell(0, 5, str(tile_hash), fill=True)
    
    if ledger:
        pdf.ln(2)
        pdf.set_font('Helvetica', 'B', 9)
        pdf.cell(0, 5, 'Ledger Entry:', new_x='LMARGIN', new_y='NEXT')
        pdf.set_font('Courier', '', 8)
        pdf.multi_cell(0, 5, f'ID: {str(ledger.ledger_id)}\nSeq: {ledger.sequence_number}\nHash: {str(ledger.entry_hash)}', fill=True)
    
    pdf.ln(5)
    
    # EU AI Act
    pdf.section_title('EU AI Act Assessment')
    pdf.set_font('Helvetica', '', 9)
    pdf.cell(40, 5, 'Category:', new_x='RIGHT')
    pdf.cell(0, 5, str(eu_ai_act.category.value), new_x='LMARGIN', new_y='NEXT')
    pdf.cell(40, 5, 'Article:', new_x='RIGHT')
    pdf.cell(0, 5, str(eu_ai_act.article_reference), new_x='LMARGIN', new_y='NEXT')
    pdf.ln(2)
    pdf.set_font('Helvetica', 'I', 8)
    pdf.set_text_color(146, 64, 14)
    pdf.multi_cell(0, 4, str(eu_ai_act.disclaimer))
    pdf.set_text_color(0, 0, 0)
    pdf.ln(5)

    # Legal Disclosures
    pdf.section_title('Legal Scope Disclosures')
    pdf.set_fill_color(255, 251, 235)
    pdf.set_font('Helvetica', 'B', 9)
    pdf.cell(0, 5, 'Scope:', new_x='LMARGIN', new_y='NEXT')
    pdf.set_font('Helvetica', '', 8)
    pdf.multi_cell(0, 4, str(legal_disclosures.weight_space_scope), fill=True)
    pdf.ln(2)
    pdf.set_font('Helvetica', 'B', 9)
    pdf.cell(0, 5, 'Out of Scope:', new_x='LMARGIN', new_y='NEXT')
    pdf.set_font('Helvetica', '', 8)
    for item in legal_disclosures.out_of_scope:
        pdf.cell(5, 4, '-')
        pdf.cell(0, 4, str(item), new_x='LMARGIN', new_y='NEXT')
    pdf.ln(2)
    pdf.set_font('Helvetica', '', 8)
    pdf.cell(0, 4, f'Version: {legal_disclosures.version}', new_x='LMARGIN', new_y='NEXT')
    
    # Output PDF
    return bytes(pdf.output())


# Legacy compatibility wrapper
WEASYPRINT_AVAILABLE = False  # Deprecated, use PDF_AVAILABLE instead

def _ensure_weasyprint_checked():
    """Deprecated: kept for backward compatibility."""
    pass


class PDFReportGenerator:
    """
    PDF report generator for PASS97 audits.
    
    Provides methods to generate complete audit reports in PDF format.
    """
    
    def __init__(self):
        self._cache: Dict[str, bytes] = {}
    
    def generate_report(
        self,
        kpis: List[KPI],
        verification: VerificationStatus,
        file_hash: str,
        anomalies: List[Anomaly],
        risk_badge: RiskBadge,
        eu_ai_act: EUAIActCompliance,
        legal_disclosures: LegalDisclosures,
        ledger: Optional[LedgerInfo] = None,
        penrose_svg: Optional[str] = None,
        filename: str = "audit_artifact",
        tile_hash: Optional[str] = None,
        cache_key: Optional[str] = None
    ) -> bytes:
        """
        Generate a complete PDF report.
        
        Args:
            kpis: KPI results
            verification: Verification status
            file_hash: File hash
            anomalies: Detected anomalies
            risk_badge: Risk assessment
            eu_ai_act: EU AI Act info
            legal_disclosures: Legal disclosures
            ledger: Ledger info
            penrose_svg: SVG visualization (not used in fpdf2 version)
            filename: Original filename
            tile_hash: Tile hash
            cache_key: Optional cache key
            
        Returns:
            PDF bytes
        """
        # Check cache
        if cache_key and cache_key in self._cache:
            return self._cache[cache_key]
        
        # Generate PDF using fpdf2
        pdf_bytes = generate_fpdf_report(
            kpis=kpis,
            verification=verification,
            file_hash=file_hash,
            anomalies=anomalies,
            risk_badge=risk_badge,
            eu_ai_act=eu_ai_act,
            legal_disclosures=legal_disclosures,
            ledger=ledger,
            filename=filename,
            tile_hash=tile_hash
        )
        
        # Cache if key provided
        if cache_key:
            self._cache[cache_key] = pdf_bytes
        
        return pdf_bytes
    
    def clear_cache(self) -> None:
        """Clear the report cache."""
        self._cache.clear()


# Global generator instance
_pdf_generator: Optional[PDFReportGenerator] = None


def get_pdf_generator() -> PDFReportGenerator:
    """Get or create the global PDF generator."""
    global _pdf_generator
    if _pdf_generator is None:
        _pdf_generator = PDFReportGenerator()
    return _pdf_generator
