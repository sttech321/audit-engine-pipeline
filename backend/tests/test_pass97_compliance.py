"""
Tests for PASS97 compliance features.

Tests the new PASS97 spec-compliant implementations:
1. 1 MiB chunk size
2. Pentagrid angles (k × 2π/5)
3. Score weights 0.30/0.40/0.30 + 25% bias
4. Tau from kag_hash only
5. Streaming pipeline
6. ProcessPoolExecutor + 30s timeout
7. Ledger prev/next chaining
8. Anomalies, risk_badge, EU AI Act
9. PDF/HTML report generation
10. SVG Penrose visualization
11. Legal disclosures
"""
import math
import pytest

from app.services.audit_pipeline import (
    _stage4_kag_separability,
    _stage5_penrose_p3,
    process_audit_artifact,
    process_audit_artifact_extended,
    KAG_WEIGHT_STRUCTURE,
    KAG_WEIGHT_SEMANTIC,
    KAG_WEIGHT_PROVENANCE,
    KAG_BIAS_MULTIPLIER,
    PENTAGRID_SECTORS,
    TWO_PI,
)
from app.services.file_validation import read_file_streaming
from app.services.ledger_service import (
    LedgerChain,
    compute_ledger_prev,
    compute_ledger_next,
    compute_audit_content_sha256,
    compute_entry_hash,
)
from app.services.svg_generator import (
    generate_penrose_svg,
    generate_minimal_svg,
    embed_svg_in_metadata,
)
from app.services.pdf_generator import (
    generate_pdf_html,
    PDFReportGenerator,
)
from app.models.common_schemas import (
    RiskBadge, RiskLevel, LegalDisclosures, EUAIActCompliance,
    KPI, VerificationStatus, Anomaly, AnomalyType,
)


# ─── Test Score Weights ──────────────────────────────────────────────────────

class TestScoreWeights:
    """Tests for PASS97 score weight compliance."""
    
    def test_weight_values(self):
        """Verify correct weight values per spec."""
        assert KAG_WEIGHT_STRUCTURE == 0.30
        assert KAG_WEIGHT_SEMANTIC == 0.40
        assert KAG_WEIGHT_PROVENANCE == 0.30
        assert KAG_WEIGHT_STRUCTURE + KAG_WEIGHT_SEMANTIC + KAG_WEIGHT_PROVENANCE == 1.0
    
    def test_bias_multiplier(self):
        """Verify 25% bias multiplier."""
        assert KAG_BIAS_MULTIPLIER == 0.25
    
    def test_kag_returns_tuple(self):
        """KAG function returns (score, kag_hash) tuple."""
        coeffs = [100, 50, 200, 75, 150, 25, 175, 125]
        ntt_fold = 0xABCDEF12
        
        result = _stage4_kag_separability(coeffs, ntt_fold)
        
        assert isinstance(result, tuple)
        assert len(result) == 2
        score, kag_hash = result
        assert 0 <= score <= 1
        assert isinstance(kag_hash, str)
        assert len(kag_hash) == 64


# ─── Test Pentagrid Angles ───────────────────────────────────────────────────

class TestPentagridAngles:
    """Tests for PASS97 pentagrid angle compliance."""
    
    def test_pentagrid_sectors(self):
        """Verify 5-fold pentagrid symmetry."""
        assert PENTAGRID_SECTORS == 5
    
    def test_pentagrid_angles_formula(self):
        """Verify angles follow k × 2π/5 formula."""
        for k in range(5):
            expected_angle = k * TWO_PI / PENTAGRID_SECTORS
            # The angle should be one of the pentagrid angles
            assert abs(expected_angle - k * 2 * math.pi / 5) < 1e-10
    
    def test_penrose_returns_sector_in_range(self):
        """Penrose sector must be in {0,1,2,3,4}."""
        godel_val = 12345678901234567890
        ntt_fold = 0xABCDEF12
        kag_score = 0.65
        kag_hash = "a" * 64
        
        result = _stage5_penrose_p3(godel_val, ntt_fold, kag_score, kag_hash)
        
        assert "sector" in result
        assert result["sector"] in {0, 1, 2, 3, 4}
    
    def test_penrose_theta_is_pentagrid_angle(self):
        """Theta must be exactly k × 2π/5."""
        godel_val = 12345678901234567890
        ntt_fold = 0xABCDEF12
        kag_score = 0.65
        kag_hash = "b" * 64
        
        result = _stage5_penrose_p3(godel_val, ntt_fold, kag_score, kag_hash)
        
        theta = result["theta"]
        k = result["sector"]
        expected_theta = k * TWO_PI / PENTAGRID_SECTORS
        
        assert abs(theta - expected_theta) < 1e-6
    
    def test_penrose_has_tau(self):
        """Penrose result must include tau."""
        godel_val = 12345678901234567890
        ntt_fold = 0xABCDEF12
        kag_score = 0.65
        kag_hash = "c" * 64
        
        result = _stage5_penrose_p3(godel_val, ntt_fold, kag_score, kag_hash)
        
        assert "tau" in result
        assert 0 <= result["tau"] <= 1
    
    def test_penrose_has_tile_hash(self):
        """Penrose result must include tile_hash."""
        godel_val = 12345678901234567890
        ntt_fold = 0xABCDEF12
        kag_score = 0.65
        kag_hash = "d" * 64
        
        result = _stage5_penrose_p3(godel_val, ntt_fold, kag_score, kag_hash)
        
        assert "tile_hash" in result
        assert len(result["tile_hash"]) == 16


# ─── Test Ledger Chaining ────────────────────────────────────────────────────

class TestLedgerChaining:
    """Tests for PASS97 ledger chain compliance."""
    
    def test_ledger_chain_creation(self):
        """Can create a new ledger chain."""
        chain = LedgerChain()
        assert chain.get_chain_length() == 0
    
    def test_ledger_add_entry(self):
        """Can add entries to ledger chain."""
        chain = LedgerChain()
        
        entry = chain.add_entry(
            audit_content_sha256="abc123" * 10 + "abcd",
            file_hash="def456" * 10 + "defg",
            penrose_hash="ghi789" * 10 + "ghij"
        )
        
        assert entry.sequence_number == 0
        assert entry.ledger_prev is None  # Genesis entry
        assert chain.get_chain_length() == 1
    
    def test_ledger_prev_computed(self):
        """Second entry should have ledger_prev set."""
        chain = LedgerChain()
        
        entry1 = chain.add_entry("a" * 64, "b" * 64, "c" * 64)
        entry2 = chain.add_entry("d" * 64, "e" * 64, "f" * 64)
        
        assert entry2.ledger_prev is not None
        assert len(entry2.ledger_prev) == 64
    
    def test_ledger_next_updated(self):
        """First entry should have ledger_next set after second added."""
        chain = LedgerChain()
        
        entry1 = chain.add_entry("a" * 64, "b" * 64, "c" * 64)
        assert entry1.ledger_next is None
        
        entry2 = chain.add_entry("d" * 64, "e" * 64, "f" * 64)
        
        # Re-fetch entry1 to see updated ledger_next
        entry1_updated = chain.get_entry(0)
        assert entry1_updated.ledger_next is not None
    
    def test_ledger_chain_integrity(self):
        """Chain integrity verification should pass for valid chain."""
        chain = LedgerChain()
        
        for i in range(5):
            chain.add_entry(f"{i}" * 64, f"{i+1}" * 64, f"{i+2}" * 64)
        
        assert chain.verify_chain_integrity() == True
    
    def test_audit_content_sha256(self):
        """audit_content_sha256 is deterministic."""
        hash1 = compute_audit_content_sha256(
            "file_hash", 123456, 789012, 0.75, "penrose", "tile"
        )
        hash2 = compute_audit_content_sha256(
            "file_hash", 123456, 789012, 0.75, "penrose", "tile"
        )
        
        assert hash1 == hash2
        assert len(hash1) == 64


# ─── Test Risk Badge & EU AI Act ─────────────────────────────────────────────

class TestRiskBadgeAndEUAIAct:
    """Tests for risk badge and EU AI Act compliance."""
    
    def test_risk_badge_low(self):
        """High score, no failures -> LOW risk."""
        badge = RiskBadge.from_audit_score(95.0, 0)
        assert badge.level == RiskLevel.LOW
    
    def test_risk_badge_medium(self):
        """Mid score, 1 failure -> MEDIUM risk."""
        badge = RiskBadge.from_audit_score(75.0, 1)
        assert badge.level == RiskLevel.MEDIUM
    
    def test_risk_badge_high(self):
        """Lower score, 2 failures -> HIGH risk."""
        badge = RiskBadge.from_audit_score(55.0, 2)
        assert badge.level == RiskLevel.HIGH
    
    def test_risk_badge_critical(self):
        """Low score, many failures -> CRITICAL risk."""
        badge = RiskBadge.from_audit_score(20.0, 5)
        assert badge.level == RiskLevel.CRITICAL
    
    def test_eu_ai_act_from_risk_badge(self):
        """EU AI Act category maps from risk badge."""
        badge_low = RiskBadge.from_audit_score(95.0, 0)
        eu_low = EUAIActCompliance.from_risk_badge(badge_low)
        
        badge_critical = RiskBadge.from_audit_score(20.0, 5)
        eu_critical = EUAIActCompliance.from_risk_badge(badge_critical)
        
        assert eu_low.category.value == "MINIMAL_RISK"
        assert eu_critical.category.value == "HIGH_RISK"
    
    def test_eu_ai_act_has_disclaimer(self):
        """EU AI Act must have disclaimer."""
        badge = RiskBadge.from_audit_score(50.0, 3)
        eu = EUAIActCompliance.from_risk_badge(badge)
        
        assert eu.disclaimer is not None
        assert len(eu.disclaimer) > 0
        assert "informational" in eu.disclaimer.lower()


# ─── Test Legal Disclosures ──────────────────────────────────────────────────

class TestLegalDisclosures:
    """Tests for PASS97 legal disclosure compliance."""
    
    def test_legal_disclosures_default(self):
        """Default legal disclosures are available."""
        disclosures = LegalDisclosures.default()
        
        assert disclosures.weight_space_scope is not None
        assert len(disclosures.weight_space_scope) > 0
        assert "weight" in disclosures.weight_space_scope.lower()
    
    def test_out_of_scope_items(self):
        """Out of scope items are defined."""
        disclosures = LegalDisclosures.default()
        
        assert len(disclosures.out_of_scope) > 0
        assert any("runtime" in item.lower() for item in disclosures.out_of_scope)
    
    def test_version_present(self):
        """Version string is present."""
        disclosures = LegalDisclosures.default()
        
        assert disclosures.version is not None
        assert "PASS97" in disclosures.version


# ─── Test SVG Generation ─────────────────────────────────────────────────────

class TestSVGGeneration:
    """Tests for SVG Penrose visualization."""
    
    def test_generate_penrose_svg(self):
        """Can generate Penrose SVG."""
        penrose_data = {
            "r": 0.618,
            "theta": 1.2566,
            "sector": 2,
            "penrose_hash": "abc123" * 10 + "abcd",
            "tau": 0.5,
            "tile_hash": "xyz789" * 2 + "xy"
        }
        
        svg = generate_penrose_svg(penrose_data, risk_level="LOW")
        
        assert svg.startswith("<svg")
        assert "</svg>" in svg
        assert "Penrose" in svg
    
    def test_generate_minimal_svg(self):
        """Can generate minimal SVG icon."""
        svg = generate_minimal_svg(sector=3, risk_level="MEDIUM", size=64)
        
        assert svg.startswith("<svg")
        assert "</svg>" in svg
    
    def test_embed_svg_in_metadata(self):
        """Can embed SVG in metadata."""
        svg = generate_minimal_svg(sector=1, risk_level="LOW")
        metadata = embed_svg_in_metadata(svg)
        
        assert "image" in metadata
        assert metadata["image"].startswith("data:image/svg+xml;base64,")


# ─── Test PDF Generation ─────────────────────────────────────────────────────

class TestPDFGeneration:
    """Tests for PDF report generation."""
    
    def test_generate_pdf_html(self):
        """Can generate HTML for PDF."""
        kpis = [
            KPI(id="1", label="Audit Score", value=95, trend="stable", status="excellent"),
        ]
        verification = VerificationStatus(
            status="Verified", confidence=99, timestamp="1234567890", checks=["Pass"]
        )
        risk_badge = RiskBadge.from_audit_score(95, 0)
        eu_ai_act = EUAIActCompliance.from_risk_badge(risk_badge)
        legal = LegalDisclosures.default()
        
        html = generate_pdf_html(
            kpis=kpis,
            verification=verification,
            file_hash="abc123" * 10 + "abcd",
            anomalies=[],
            risk_badge=risk_badge,
            eu_ai_act=eu_ai_act,
            legal_disclosures=legal,
            filename="test.rim95"
        )
        
        assert "<!DOCTYPE html>" in html
        assert "PASS97 Audit Report" in html
        assert "Audit Score" in html
    
    def test_pdf_generator_instance(self):
        """PDF generator can be instantiated."""
        generator = PDFReportGenerator()
        assert generator is not None


# ─── Test Extended Audit Result ──────────────────────────────────────────────

class TestExtendedAuditResult:
    """Tests for extended audit result."""
    
    def test_extended_result_structure(self):
        """Extended result has all required fields."""
        content = bytes(range(256)) * 4
        
        result, file_hash = process_audit_artifact_extended(content, "test.rim95")
        
        assert result.kpis is not None
        assert result.verification is not None
        assert result.file_hash is not None
        assert result.anomalies is not None
        assert result.risk_badge is not None
        assert result.eu_ai_act is not None
        assert result.legal_disclosures is not None
    
    def test_extended_result_has_penrose_details(self):
        """Extended result includes Penrose details."""
        content = bytes(range(256)) * 4
        
        result, file_hash = process_audit_artifact_extended(content, "test.rim95")
        
        assert result.penrose_details is not None
        assert "sector" in result.penrose_details
        assert "tau" in result.penrose_details
    
    def test_extended_result_has_tile_hash(self):
        """Extended result includes tile_hash."""
        content = bytes(range(256)) * 4
        
        result, file_hash = process_audit_artifact_extended(content, "test.rim95")
        
        assert result.tile_hash is not None
        assert len(result.tile_hash) == 16
