"""
Tests for SHA-256 hash computation.
These tests verify that hashing behavior is preserved and consistent.
"""
import hashlib

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.audit_pipeline import process_audit_artifact
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

def test_pipeline_hash_correct(sample_valid_content):
    """Pipeline should compute correct SHA-256 hash."""
    expected = hashlib.sha256(sample_valid_content).hexdigest()
    
    kpis, verification, file_hash = process_audit_artifact(
        sample_valid_content, 
        "test.rim95"
    )
    
    assert file_hash == expected


def test_pipeline_hash_deterministic(sample_valid_content):
    """Pipeline hash should be deterministic."""
    _, _, hash1 = process_audit_artifact(sample_valid_content, "test.rim95")
    _, _, hash2 = process_audit_artifact(sample_valid_content, "test.rim95")
    
    assert hash1 == hash2


def test_pipeline_hash_independent_of_filename(sample_valid_content):
    """Hash should depend on content, not filename."""
    _, _, hash1 = process_audit_artifact(sample_valid_content, "file1.rim95")
    _, _, hash2 = process_audit_artifact(sample_valid_content, "file2.rim95")
    
    assert hash1 == hash2


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
