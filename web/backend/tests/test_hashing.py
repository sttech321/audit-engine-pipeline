"""
Tests for SHA-256 hash computation.
These tests verify that hashing behavior is preserved and consistent.
"""
import hashlib
import os
import tempfile

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.rim_wrapper import run_rim_audit
from app.services.file_validation import compute_file_hash
from tests.conftest import make_file

client = TestClient(app)


# ─── Basic Hash Tests ────────────────────────────────────────────────────────

def test_hash_computation_correct():
    """compute_file_hash should produce correct SHA-256."""
    content = b"test content for hashing"
    expected = hashlib.sha256(content).hexdigest()
    
    result = compute_file_hash(content)
    
    assert result == expected


def test_hash_is_64_char_hex():
    """Hash should be 64-character lowercase hex string."""
    content = bytes(range(256))
    
    result = compute_file_hash(content)
    
    assert len(result) == 64
    assert result == result.lower()
    assert all(c in "0123456789abcdef" for c in result)


def test_hash_deterministic():
    """Same content should always produce same hash."""
    content = bytes(range(256)) * 4
    
    hash1 = compute_file_hash(content)
    hash2 = compute_file_hash(content)
    
    assert hash1 == hash2


def test_hash_different_content():
    """Different content should produce different hashes."""
    content1 = b"content version 1"
    content2 = b"content version 2"
    
    hash1 = compute_file_hash(content1)
    hash2 = compute_file_hash(content2)
    
    assert hash1 != hash2


def test_hash_empty_content():
    """Empty content should produce valid hash."""
    expected = hashlib.sha256(b"").hexdigest()
    
    result = compute_file_hash(b"")
    
    assert result == expected


# ─── Pipeline Hash Tests ─────────────────────────────────────────────────────

def test_rimos_audit_content_hash_deterministic(sample_valid_content):
    """RIM-OS audit_content_sha256 should be deterministic for the same path+content."""
    suffix = ".rim95"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        tmp.write(sample_valid_content)
        tmp_path = tmp.name
        tmp.close()

        report1 = run_rim_audit(tmp_path)
        report2 = run_rim_audit(tmp_path)
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass

    integrity1 = report1.get("integrity", {}) or {}
    integrity2 = report2.get("integrity", {}) or {}
    h1 = integrity1.get("audit_content_sha256", "")
    h2 = integrity2.get("audit_content_sha256", "")
    assert h1 and h1 == h2


def test_rimos_audit_hash_changes_with_different_paths(sample_valid_content):
    """
    RIM-OS audit_content_sha256 includes input path in its scope,
    so different paths for the same bytes may yield different hashes.
    """
    def _run(contents: bytes, name: str) -> str:
        suffix = os.path.splitext(name)[1] or ".bin"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(contents)
            path = tmp.name
        try:
            report = run_rim_audit(path)
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass
        integrity = report.get("integrity", {}) or {}
        return integrity.get("audit_content_sha256", "")

    h1 = _run(sample_valid_content, "file1.rim95")
    h2 = _run(sample_valid_content, "file2.rim95")
    assert h1 and h2 and h1 != h2


# ─── API Hash Tests ──────────────────────────────────────────────────────────

def test_api_returns_correct_hash(sample_valid_content):
    """API should return correct file hash."""
    expected = hashlib.sha256(sample_valid_content).hexdigest()
    
    r = client.post("/api/upload", files=make_file("test.rim95", sample_valid_content))
    
    assert r.status_code == 200
    assert r.json()["fileHash"] == expected


def test_api_hash_consistent_across_uploads(sample_valid_content):
    """Same file uploaded multiple times should have same hash."""
    from app.services.abuse_protection import clear_stores
    
    r1 = client.post("/api/upload", files=make_file("test.rim95", sample_valid_content))
    clear_stores()  # Clear stores to allow same content upload
    r2 = client.post("/api/upload", files=make_file("test.rim95", sample_valid_content))
    
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["fileHash"] == r2.json()["fileHash"]


def test_api_hash_format(sample_valid_content):
    """API hash should be properly formatted."""
    r = client.post("/api/upload", files=make_file("test.rim95", sample_valid_content))
    
    assert r.status_code == 200
    file_hash = r.json()["fileHash"]
    
    assert len(file_hash) == 64
    assert file_hash == file_hash.lower()
    assert all(c in "0123456789abcdef" for c in file_hash)


# ─── Edge Cases ──────────────────────────────────────────────────────────────

def test_hash_large_content():
    """Should hash large content correctly."""
    # 100KB of varied content
    content = bytes(range(256)) * 400
    expected = hashlib.sha256(content).hexdigest()
    
    result = compute_file_hash(content)
    
    assert result == expected


def test_hash_binary_content():
    """Should hash binary content correctly."""
    # Binary content with all byte values
    content = bytes(range(256))
    expected = hashlib.sha256(content).hexdigest()
    
    result = compute_file_hash(content)
    
    assert result == expected


def test_hash_unicode_bytes():
    """Should hash UTF-8 encoded content correctly."""
    text = "Hello, 世界! 🌍"
    content = text.encode("utf-8")
    expected = hashlib.sha256(content).hexdigest()
    
    result = compute_file_hash(content)
    
    assert result == expected
