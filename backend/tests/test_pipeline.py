"""
Tests for the audit pipeline service.
"""
import pytest

from app.services.audit_pipeline import (
    _stage1_godel_fingerprint,
    _stage2_padic_lift,
    _stage3_ntt_fingerprint,
    _stage4_kag_separability,
    _validate_rim95_format,
    process_audit_artifact,
)


# ─── FORMAT VALIDATION TESTS ─────────────────────────────────────────────────

def test_validate_rim95_empty_file():
    """Empty files should fail validation."""
    is_valid, reason = _validate_rim95_format(b"", "test.rim95")
    assert not is_valid
    assert "too small" in reason.lower()


def test_validate_rim95_low_diversity():
    """Files with low byte diversity should fail."""
    # Repeating single byte
    is_valid, reason = _validate_rim95_format(b"A" * 100, "test.rim95")
    assert not is_valid
    assert "diversity" in reason.lower() or "entropy" in reason.lower()


def test_validate_rim95_valid_content():
    """Valid binary content should pass."""
    content = bytes(range(256)) * 4  # High diversity content
    is_valid, reason = _validate_rim95_format(content, "test.rim95")
    assert is_valid


# ─── PIPELINE STAGE TESTS ────────────────────────────────────────────────────

def test_godel_fingerprint_deterministic():
    """Same content should produce same Gödel fingerprint."""
    content = bytes(range(256))
    fp1 = _stage1_godel_fingerprint(content)
    fp2 = _stage1_godel_fingerprint(content)
    assert fp1 == fp2


def test_godel_fingerprint_different_content():
    """Different content should produce different fingerprints."""
    fp1 = _stage1_godel_fingerprint(b"content_a")
    fp2 = _stage1_godel_fingerprint(b"content_b")
    assert fp1 != fp2


def test_padic_lift_length():
    """p-adic lift should return 8 coefficients."""
    coeffs = _stage2_padic_lift(12345678)
    assert len(coeffs) == 8


def test_ntt_fingerprint_deterministic():
    """NTT fingerprint should be deterministic."""
    content = bytes(range(256))
    fp1 = _stage3_ntt_fingerprint(content)
    fp2 = _stage3_ntt_fingerprint(content)
    assert fp1 == fp2


def test_kag_score_range():
    """KAG score should be between 0 and 1, kag_hash should be valid."""
    coeffs = [100, 50, 200, 75, 150, 25, 175, 125]
    ntt_fold = 0xABCDEF12
    result = _stage4_kag_separability(coeffs, ntt_fold)
    # New API returns (score, kag_hash) tuple
    assert isinstance(result, tuple)
    score, kag_hash = result
    assert 0 <= score <= 1
    assert isinstance(kag_hash, str)
    assert len(kag_hash) == 64  # SHA-256 hex


# ─── FULL PIPELINE TESTS ─────────────────────────────────────────────────────

def test_process_audit_artifact_returns_tuple():
    """Pipeline should return (kpis, verification, file_hash)."""
    content = bytes(range(256)) * 4
    result = process_audit_artifact(content, "test.rim95")
    assert isinstance(result, tuple)
    assert len(result) == 3


def test_process_audit_artifact_deterministic():
    """Same content should produce same results."""
    content = bytes(range(256)) * 4
    kpis1, ver1, hash1 = process_audit_artifact(content, "test.rim95")
    kpis2, ver2, hash2 = process_audit_artifact(content, "test.rim95")
    
    assert hash1 == hash2
    assert ver1.status == ver2.status
    assert ver1.confidence == ver2.confidence


def test_process_audit_artifact_valid_content():
    """Valid content should produce verification result."""
    content = bytes(range(256)) * 4
    kpis, verification, file_hash = process_audit_artifact(content, "test.rim95")
    
    assert len(file_hash) == 64  # SHA-256 hex
    assert verification.status in ["Verified", "Verified with Warnings", "Verification Failed"]
    assert 0 <= verification.confidence <= 100
    assert len(kpis) == 5
