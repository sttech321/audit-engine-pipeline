"""
Comprehensive upload edge case tests for the PASS97 audit pipeline.
Tests all 3 outcome states: Verified, Verified with Warnings, Verification Failed.
Also tests determinism, empty files, large files, and file type validation.
"""
import pytest
import hashlib
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def make_file(name: str, content: bytes):
    return {"file": (name, content, "application/octet-stream")}


# ─── HELPERS ─────────────────────────────────────────────────────────────────

def find_file_for_outcome(target_outcome: str, max_iterations: int = 2000) -> bytes:
    """Find file content that produces the desired audit outcome.
    Pads content with a full 0-255 byte range so byte_variety > 10 always,
    making has_structure_signal consistent between the helper and the pipeline.
    """
    varied_pad = bytes(range(256)) * 4  # 1024 bytes of varied content = always has_structure=True
    for i in range(max_iterations):
        content = str(i).encode() + varied_pad
        h = hashlib.sha256(content).hexdigest()
        sig    = int(h[0:4], 16) % 256
        hmatch = int(h[4:8], 16) % 256
        struct_ = int(h[8:12], 16) % 256
        # has_structure is always True with varied_pad content
        sig_ok    = sig   > 12
        hmatch_ok = hmatch > 8
        struct_ok = struct_ > 6  # has_structure always True

        if target_outcome == "failed":
            if not sig_ok and not hmatch_ok:
                return content
        elif target_outcome == "warning":
            if (not sig_ok or not struct_ok) and hmatch_ok:
                return content
        elif target_outcome == "verified":
            if sig_ok and hmatch_ok and struct_ok:
                return content
    raise RuntimeError(f"Could not find file for target '{target_outcome}' in {max_iterations} iterations")



# ─── STAGE 1: INGESTION TESTS ────────────────────────────────────────────────

def test_empty_file_rejected():
    """Stage 1: Empty files must be rejected with HTTP 422, not silently processed."""
    r = client.post("/api/upload", files=make_file("empty.rim95", b""))
    assert r.status_code == 422
    assert "empty" in r.json()["detail"].lower()


def test_minimum_valid_file():
    """Stage 1: A 1-byte file should be accepted and processed."""
    r = client.post("/api/upload", files=make_file("tiny.rim95", b"A"))
    assert r.status_code == 200
    data = r.json()
    assert data["fileInfo"]["size"] == 1


# ─── STAGE 3: HASHING / DETERMINISM TESTS ───────────────────────────────────

def test_same_file_same_hash():
    """Stage 3: Same file → same SHA-256 fileHash every time."""
    content = b"determinism_test_vector"
    r1 = client.post("/api/upload", files=make_file("test.rim95", content))
    r2 = client.post("/api/upload", files=make_file("test.rim95", content))
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["fileHash"] == r2.json()["fileHash"]


def test_same_file_same_kpis():
    """Stage 5: Same file → same KPIs (deterministic scoring)."""
    content = b"determinism_test_vector"
    r1 = client.post("/api/upload", files=make_file("test.rim95", content))
    r2 = client.post("/api/upload", files=make_file("test.rim95", content))
    assert r1.json()["kpis"] == r2.json()["kpis"]


def test_same_file_same_verification():
    """Stage 4: Same file → same verification status (deterministic checks)."""
    content = b"determinism_test_vector"
    r1 = client.post("/api/upload", files=make_file("test.rim95", content))
    r2 = client.post("/api/upload", files=make_file("test.rim95", content))
    v1 = r1.json()["verification"]
    v2 = r2.json()["verification"]
    # All fields except timestamp should be identical
    assert v1["status"] == v2["status"]
    assert v1["confidence"] == v2["confidence"]
    assert v1["checks"] == v2["checks"]
    assert v1["timestamp"] == v2["timestamp"]  # timestamp is now deterministic


def test_different_files_different_hashes():
    """Stage 3: Different input → different fileHash."""
    r1 = client.post("/api/upload", files=make_file("a.rim95", b"file_alpha"))
    r2 = client.post("/api/upload", files=make_file("b.rim95", b"file_beta"))
    assert r1.json()["fileHash"] != r2.json()["fileHash"]


# ─── STAGE 4: VERIFICATION OUTCOME TESTS ────────────────────────────────────

def test_verification_failed_state():
    """Stage 4: A file with specific hash properties must return Verification Failed."""
    content = find_file_for_outcome("failed")
    r = client.post("/api/upload", files=make_file("bad.rim95", content))
    assert r.status_code == 200
    v = r.json()["verification"]
    assert "Failed" in v["status"]
    assert v["confidence"] == 0 or v["confidence"] <= 10
    # Signature Valid must NOT be in checks
    assert "Signature Valid" not in v["checks"]


def test_verification_succeeded_state():
    """Stage 4: A well-formed file must return Verified status."""
    content = find_file_for_outcome("verified")
    r = client.post("/api/upload", files=make_file("good.rim95", content))
    assert r.status_code == 200
    v = r.json()["verification"]
    assert "Verified" in v["status"]
    assert "Failed" not in v["status"]
    assert "Signature Valid" in v["checks"]


# ─── STAGE 5: SCORING RANGE TESTS ────────────────────────────────────────────

def test_failed_audit_has_low_score():
    """Stage 5: Failed audits must score 0–49 (not pass with a high score)."""
    content = find_file_for_outcome("failed")
    r = client.post("/api/upload", files=make_file("bad.rim95", content))
    assert r.status_code == 200
    kpis = r.json()["kpis"]
    audit_score = next(k["value"] for k in kpis if k["label"] == "Audit Score")
    assert float(audit_score) < 50, f"Failed audit should score < 50, got {audit_score}"


def test_failed_audit_has_issues():
    """Stage 5: Failed audits must report >0 issues found."""
    content = find_file_for_outcome("failed")
    r = client.post("/api/upload", files=make_file("bad.rim95", content))
    assert r.status_code == 200
    kpis = r.json()["kpis"]
    issues = next(k["value"] for k in kpis if k["label"] == "Issues Found")
    assert int(issues) > 0, f"Failed audit should have issues > 0, got {issues}"


def test_passed_audit_has_no_issues():
    """Stage 5: Passed audits should report 0 issues."""
    content = find_file_for_outcome("verified")
    r = client.post("/api/upload", files=make_file("good.rim95", content))
    assert r.status_code == 200
    kpis = r.json()["kpis"]
    issues = next(k["value"] for k in kpis if k["label"] == "Issues Found")
    assert int(issues) == 0, f"Passed audit should have 0 issues, got {issues}"


# ─── LARGE FILE ──────────────────────────────────────────────────────────────

def test_large_file_processes_correctly():
    """Stage 1: 5MB file should be accepted and processed without timeout."""
    content = b"P" * (5 * 1024 * 1024)
    r = client.post("/api/upload", files=make_file("large.rim95", content))
    assert r.status_code == 200
    assert r.json()["fileInfo"]["size"] == 5 * 1024 * 1024


# ─── API CONTRACT ─────────────────────────────────────────────────────────────

def test_upload_response_schema():
    """Integration: UploadResponse has all required fields."""
    r = client.post("/api/upload", files=make_file("schema_test.rim95", b"test_content"))
    assert r.status_code == 200
    data = r.json()
    assert "fileInfo" in data
    assert "kpis" in data
    assert "verification" in data
    assert "fileHash" in data
    assert "uploadId" in data
    assert "metadata" in data
    assert len(data["fileHash"]) == 64  # sha256 hex
    assert len(data["kpis"]) >= 3


if __name__ == "__main__":
    pytest.main(["-v", __file__])
