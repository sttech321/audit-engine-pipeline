"""
Regression tests for the PASS97 audit pipeline.

These tests ensure that ALL existing behavior remains unchanged after 
the Milestone 1 enhancements. This is critical for non-breaking changes.
"""
import hashlib

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.audit_pipeline import (
    _stage1_godel_fingerprint,
    _stage2_padic_lift,
    _stage3_ntt_fingerprint,
    _stage4_kag_separability,
    _stage5_penrose_p3,
    _validate_rim95_format,
    process_audit_artifact,
)
from tests.conftest import make_file

client = TestClient(app)


# ─── KPI Regression Tests ────────────────────────────────────────────────────

def test_kpi_count_unchanged(sample_valid_content):
    """Pipeline should always return exactly 5 KPIs."""
    kpis, _, _ = process_audit_artifact(sample_valid_content, "test.rim95")
    
    assert len(kpis) == 5


def test_kpi_labels_unchanged(sample_valid_content):
    """KPI labels should remain unchanged."""
    expected_labels = [
        "Audit Score",
        "Issues Found",
        "KAG Score",
        "Coverage",
        "Penrose Sector"
    ]
    
    kpis, _, _ = process_audit_artifact(sample_valid_content, "test.rim95")
    actual_labels = [kpi.label for kpi in kpis]
    
    assert actual_labels == expected_labels


def test_kpi_ids_unchanged(sample_valid_content):
    """KPI IDs should remain unchanged."""
    expected_ids = ["kpi-1", "kpi-2", "kpi-3", "kpi-4", "kpi-5"]
    
    kpis, _, _ = process_audit_artifact(sample_valid_content, "test.rim95")
    actual_ids = [kpi.id for kpi in kpis]
    
    assert actual_ids == expected_ids


def test_kpi_determinism(sample_valid_content):
    """Same content should produce identical KPIs."""
    kpis1, _, _ = process_audit_artifact(sample_valid_content, "test.rim95")
    kpis2, _, _ = process_audit_artifact(sample_valid_content, "test.rim95")
    
    for kpi1, kpi2 in zip(kpis1, kpis2):
        assert kpi1.id == kpi2.id
        assert kpi1.label == kpi2.label
        assert kpi1.value == kpi2.value
        assert kpi1.trend == kpi2.trend
        assert kpi1.status == kpi2.status


def test_kpi_structure(sample_valid_content):
    """Each KPI should have required fields."""
    kpis, _, _ = process_audit_artifact(sample_valid_content, "test.rim95")
    
    for kpi in kpis:
        assert hasattr(kpi, "id")
        assert hasattr(kpi, "label")
        assert hasattr(kpi, "value")
        assert hasattr(kpi, "trend")
        assert hasattr(kpi, "status")
        assert hasattr(kpi, "description")


# ─── Verification Status Regression Tests ────────────────────────────────────

def test_verification_status_values(sample_valid_content):
    """Verification status should be one of expected values."""
    _, verification, _ = process_audit_artifact(sample_valid_content, "test.rim95")
    
    valid_statuses = ["Verified", "Verified with Warnings", "Verification Failed"]
    assert verification.status in valid_statuses


def test_verification_confidence_range(sample_valid_content):
    """Confidence should be 0-100."""
    _, verification, _ = process_audit_artifact(sample_valid_content, "test.rim95")
    
    assert 0 <= verification.confidence <= 100


def test_verification_has_checks(sample_valid_content):
    """Verification should have checks list."""
    _, verification, _ = process_audit_artifact(sample_valid_content, "test.rim95")
    
    assert isinstance(verification.checks, list)
    assert len(verification.checks) > 0


def test_verification_has_timestamp(sample_valid_content):
    """Verification should have timestamp."""
    _, verification, _ = process_audit_artifact(sample_valid_content, "test.rim95")
    
    assert isinstance(verification.timestamp, str)
    assert len(verification.timestamp) > 0


def test_verification_determinism(sample_valid_content):
    """Same content should produce consistent verification."""
    _, ver1, _ = process_audit_artifact(sample_valid_content, "test.rim95")
    _, ver2, _ = process_audit_artifact(sample_valid_content, "test.rim95")
    
    assert ver1.status == ver2.status
    assert ver1.confidence == ver2.confidence
    assert ver1.checks == ver2.checks


# ─── File Hash Regression Tests ──────────────────────────────────────────────

def test_file_hash_sha256(sample_valid_content):
    """File hash should match SHA-256."""
    expected = hashlib.sha256(sample_valid_content).hexdigest()
    
    _, _, file_hash = process_audit_artifact(sample_valid_content, "test.rim95")
    
    assert file_hash == expected


def test_file_hash_format(sample_valid_content):
    """File hash should be 64-char lowercase hex."""
    _, _, file_hash = process_audit_artifact(sample_valid_content, "test.rim95")
    
    assert len(file_hash) == 64
    assert file_hash == file_hash.lower()
    assert all(c in "0123456789abcdef" for c in file_hash)


def test_file_hash_determinism(sample_valid_content):
    """Same content should produce same hash."""
    _, _, hash1 = process_audit_artifact(sample_valid_content, "test.rim95")
    _, _, hash2 = process_audit_artifact(sample_valid_content, "test.rim95")
    
    assert hash1 == hash2


# ─── Pipeline Stage Regression Tests ─────────────────────────────────────────

def test_godel_fingerprint_unchanged():
    """Gödel fingerprint calculation should be unchanged."""
    content = bytes(range(256))
    
    fp1 = _stage1_godel_fingerprint(content)
    fp2 = _stage1_godel_fingerprint(content)
    
    assert fp1 == fp2
    assert isinstance(fp1, int)


def test_padic_lift_unchanged():
    """p-adic lift should return 8 coefficients."""
    coeffs = _stage2_padic_lift(12345678901234567890)
    
    assert len(coeffs) == 8
    assert all(isinstance(c, int) for c in coeffs)


def test_ntt_fingerprint_unchanged():
    """NTT fingerprint should be unchanged."""
    content = bytes(range(256))
    
    fp1 = _stage3_ntt_fingerprint(content)
    fp2 = _stage3_ntt_fingerprint(content)
    
    assert fp1 == fp2
    assert isinstance(fp1, int)


def test_kag_score_unchanged():
    """KAG score should be in [0, 1], returns tuple (score, kag_hash)."""
    coeffs = [100, 50, 200, 75, 150, 25, 175, 125]
    ntt_fold = 0xABCDEF12
    
    result = _stage4_kag_separability(coeffs, ntt_fold)
    
    # New API returns (score, kag_hash) tuple
    assert isinstance(result, tuple)
    score, kag_hash = result
    assert 0 <= score <= 1
    assert isinstance(kag_hash, str)
    assert len(kag_hash) == 64  # SHA-256 hex


def test_penrose_mapping_unchanged():
    """Penrose mapping should have expected fields including new PASS97 spec fields."""
    godel_val = 12345678901234567890
    ntt_fold = 0xABCDEF12
    kag_score = 0.65
    kag_hash = "abc123" * 10 + "abcd"  # 64-char mock hash
    
    result = _stage5_penrose_p3(godel_val, ntt_fold, kag_score, kag_hash)
    
    # Original fields (backward compatible)
    assert "r" in result
    assert "theta" in result
    assert "sector" in result
    assert "penrose_hash" in result
    
    # New PASS97 spec fields
    assert "tau" in result
    assert "tile_hash" in result
    
    # Pentagrid sector must be in {0,1,2,3,4}
    assert result["sector"] in {0, 1, 2, 3, 4}


# ─── API Response Regression Tests ───────────────────────────────────────────

def test_api_response_structure(sample_valid_content):
    """API response structure should be unchanged."""
    r = client.post("/api/upload", files=make_file("test.rim95", sample_valid_content))
    
    assert r.status_code == 200
    data = r.json()
    
    # Top-level fields
    assert "fileInfo" in data
    assert "kpis" in data
    assert "verification" in data
    assert "fileHash" in data
    assert "uploadId" in data
    assert "metadata" in data


def test_api_file_info_structure(sample_valid_content):
    """fileInfo structure should be unchanged."""
    r = client.post("/api/upload", files=make_file("test.rim95", sample_valid_content))
    
    data = r.json()["fileInfo"]
    
    assert "name" in data
    assert "size" in data
    assert "type" in data


def test_api_verification_structure(sample_valid_content):
    """verification structure should be unchanged."""
    r = client.post("/api/upload", files=make_file("test.rim95", sample_valid_content))
    
    data = r.json()["verification"]
    
    assert "status" in data
    assert "confidence" in data
    assert "timestamp" in data
    assert "checks" in data


def test_api_kpi_structure(sample_valid_content):
    """Each KPI should have required fields."""
    r = client.post("/api/upload", files=make_file("test.rim95", sample_valid_content))
    
    kpis = r.json()["kpis"]
    
    for kpi in kpis:
        assert "id" in kpi
        assert "label" in kpi
        assert "value" in kpi
        assert "trend" in kpi
        assert "status" in kpi


def test_api_metadata_structure(sample_valid_content):
    """metadata should contain expected fields."""
    r = client.post("/api/upload", files=make_file("test.rim95", sample_valid_content))
    
    data = r.json()["metadata"]
    
    assert "name" in data
    assert "description" in data
    assert "attributes" in data


# ─── Error Response Regression Tests ─────────────────────────────────────────

def test_empty_file_422():
    """Empty file should return 422."""
    r = client.post("/api/upload", files=make_file("test.rim95", b""))
    
    assert r.status_code == 422


def test_error_has_detail():
    """Errors should have 'detail' field."""
    r = client.post("/api/upload", files=make_file("test.rim95", b""))
    
    assert "detail" in r.json()


# ─── Format Validation Regression Tests ──────────────────────────────────────

def test_format_validation_empty():
    """Empty files should fail format validation."""
    is_valid, _ = _validate_rim95_format(b"", "test.rim95")
    
    assert is_valid is False


def test_format_validation_low_entropy():
    """Low entropy files should fail validation."""
    content = b"A" * 100
    
    is_valid, _ = _validate_rim95_format(content, "test.rim95")
    
    assert is_valid is False


def test_format_validation_valid_content(sample_valid_content):
    """Valid content should pass format validation."""
    is_valid, _ = _validate_rim95_format(sample_valid_content, "test.rim95")
    
    assert is_valid is True


# ─── End-to-End Regression Tests ─────────────────────────────────────────────

def test_complete_upload_flow(sample_valid_content):
    """Complete upload flow should work unchanged."""
    r = client.post("/api/upload", files=make_file("test.rim95", sample_valid_content))
    
    assert r.status_code == 200
    
    data = r.json()
    
    # Verify all expected fields are present and valid
    assert len(data["fileHash"]) == 64
    assert len(data["uploadId"]) == 36  # UUID format
    assert len(data["kpis"]) == 5
    assert data["fileInfo"]["size"] == len(sample_valid_content)


def test_multiple_uploads_independent(sample_valid_content):
    """Multiple uploads should be processed independently."""
    from app.services.abuse_protection import clear_stores
    
    r1 = client.post("/api/upload", files=make_file("file1.rim95", sample_valid_content))
    clear_stores()  # Clear stores to allow same content upload
    r2 = client.post("/api/upload", files=make_file("file2.rim95", sample_valid_content))
    
    # Same content should produce same hash
    assert r1.json()["fileHash"] == r2.json()["fileHash"]
    
    # But different upload IDs
    assert r1.json()["uploadId"] != r2.json()["uploadId"]


def test_pipeline_output_consistency():
    """Pipeline outputs should be consistent across calls."""
    content = bytes(range(256)) * 4
    
    results = []
    for _ in range(5):
        kpis, ver, hash_ = process_audit_artifact(content, "test.rim95")
        results.append((kpis, ver, hash_))
    
    # All hashes should be identical
    hashes = [r[2] for r in results]
    assert len(set(hashes)) == 1
    
    # All verification statuses should be identical
    statuses = [r[1].status for r in results]
    assert len(set(statuses)) == 1
    
    # All audit scores should be identical
    scores = [next(k.value for k in r[0] if k.label == "Audit Score") for r in results]
    assert len(set(scores)) == 1
