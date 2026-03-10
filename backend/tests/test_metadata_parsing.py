"""
Tests for metadata parsing from .lm3z, .rim0, and .rim95 artifact formats.
These tests verify the ADDITIVE metadata parsing functionality.
"""
import json
import struct

import pytest

from app.models.metadata_schemas import ArtifactFormat, ArtifactMetadata
from app.services.metadata_parser import (
    detect_format,
    parse_metadata,
    validate_metadata,
    _parse_lm3z,
    _parse_rim0,
    _parse_rim95,
    _parse_raw_binary,
)


# ─── Format Detection Tests ──────────────────────────────────────────────────

def test_detect_lm3z_by_magic():
    """Should detect LM3Z format by magic bytes."""
    content = b"LM3Z" + bytes(100)
    assert detect_format(content, "test.bin") == ArtifactFormat.LM3Z


def test_detect_rim0_by_magic():
    """Should detect RIM0 format by magic bytes."""
    content = b"RIM0" + bytes(100)
    assert detect_format(content, "test.bin") == ArtifactFormat.RIM0


def test_detect_rim95_by_magic():
    """Should detect RIM95 format by magic bytes."""
    content = b"R95\x00" + bytes(100)
    assert detect_format(content, "test.bin") == ArtifactFormat.RIM95


def test_detect_strict_requires_magic_lm3z():
    """STRICT: Should NOT detect format by extension alone - requires magic bytes."""
    content = bytes(100)  # No magic bytes
    # Strict mode: extension is NOT enough, must have magic bytes
    assert detect_format(content, "test.lm3z") == ArtifactFormat.UNKNOWN


def test_detect_strict_requires_magic_rim0():
    """STRICT: Should NOT detect format by extension alone - requires magic bytes."""
    content = bytes(100)
    assert detect_format(content, "test.rim0") == ArtifactFormat.UNKNOWN


def test_detect_strict_requires_magic_rim95():
    """STRICT: Should NOT detect format by extension alone - requires magic bytes."""
    content = bytes(100)
    assert detect_format(content, "test.rim95") == ArtifactFormat.UNKNOWN


def test_detect_unknown_format():
    """Should return UNKNOWN for unrecognized formats."""
    content = b"XXXX" + bytes(100)
    assert detect_format(content, "test.xyz") == ArtifactFormat.UNKNOWN


# ─── LM3Z Parsing Tests ──────────────────────────────────────────────────────

def test_parse_lm3z_valid(sample_lm3z_content):
    """Should parse valid LM3Z content correctly."""
    result = parse_metadata(sample_lm3z_content, "test.lm3z")
    
    assert result.success is True
    assert result.metadata is not None
    assert result.metadata.format_type == ArtifactFormat.LM3Z
    assert result.metadata.version == "1.0"
    assert result.metadata.artifact_id == "test-artifact-001"
    assert result.metadata.public_key is not None
    assert len(result.metadata.public_key) == 32
    assert result.metadata.signature is not None
    assert len(result.metadata.signature) == 64


def test_parse_lm3z_too_small():
    """Should fail for LM3Z files that are too small."""
    content = b"LM3Z" + bytes(10)  # Too small
    result = _parse_lm3z(content, "test.lm3z")
    
    assert result.success is False
    assert result.error_code == "METADATA_INVALID_FORMAT"


def test_parse_lm3z_invalid_magic():
    """Should fail for files without LM3Z magic."""
    content = b"XXXX" + bytes(200)
    result = _parse_lm3z(content, "test.lm3z")
    
    assert result.success is False
    assert "magic" in result.error_message.lower()


# ─── RIM0 Parsing Tests ──────────────────────────────────────────────────────

def test_parse_rim0_valid(sample_rim0_content):
    """Should parse valid RIM0 content correctly."""
    result = parse_metadata(sample_rim0_content, "test.rim0")
    
    assert result.success is True
    assert result.metadata is not None
    assert result.metadata.format_type == ArtifactFormat.RIM0
    assert result.metadata.public_key is not None
    assert result.metadata.signature is not None
    assert result.raw_payload is not None


def test_parse_rim0_too_small():
    """Should fail for RIM0 files that are too small."""
    content = b"RIM0" + bytes(10)
    result = _parse_rim0(content, "test.rim0")
    
    assert result.success is False
    assert result.error_code == "METADATA_INVALID_FORMAT"


def test_parse_rim0_invalid_magic():
    """Should fail for files without RIM0 magic."""
    content = b"XXXX" + bytes(200)
    result = _parse_rim0(content, "test.rim0")
    
    assert result.success is False


# ─── RIM95 Parsing Tests ─────────────────────────────────────────────────────

def test_parse_rim95_valid(sample_rim95_content):
    """Should parse valid RIM95 content correctly."""
    result = parse_metadata(sample_rim95_content, "test.rim95")
    
    assert result.success is True
    assert result.metadata is not None
    assert result.metadata.format_type == ArtifactFormat.RIM95
    assert result.metadata.version == "95.0"
    assert result.metadata.artifact_id == "test-rim95-001"


def test_parse_rim95_strict_requires_magic():
    """STRICT: Should reject RIM95 files without proper magic bytes."""
    # Raw binary content (no magic bytes) - strict mode rejects this
    content = bytes(range(256)) * 4
    result = parse_metadata(content, "test.rim95", strict=True)
    
    # Strict mode: should fail because magic bytes are missing
    assert result.success is False
    assert result.error_code == "METADATA_UNKNOWN_FORMAT"


def test_parse_rim95_nonstrict_allows_raw():
    """NON-STRICT: Should handle RIM95 files without magic as raw binary."""
    # Raw binary content (no magic bytes) - non-strict fallback to raw
    content = bytes(range(256)) * 4
    result = parse_metadata(content, "test.rim95", strict=False)
    
    # Non-strict mode: should succeed as raw binary
    assert result.success is True
    assert result.metadata.version == "raw"


# ─── Raw Binary Parsing Tests ────────────────────────────────────────────────

def test_parse_raw_binary():
    """Should parse raw binary files for backward compatibility."""
    content = bytes(range(256)) * 4
    result = _parse_raw_binary(content, "test.rim95")
    
    assert result.success is True
    assert result.metadata is not None
    assert result.metadata.version == "raw"
    assert result.metadata.public_key is None
    assert result.metadata.signature is None
    assert result.raw_payload == content


def test_parse_raw_binary_hash():
    """Raw binary parsing should compute correct content hash."""
    import hashlib
    
    content = bytes(range(256)) * 4
    expected_hash = hashlib.sha256(content).hexdigest()
    
    result = _parse_raw_binary(content, "test.rim95")
    
    assert result.metadata.content_hash == expected_hash


# ─── Metadata Validation Tests ───────────────────────────────────────────────

def test_validate_metadata_complete():
    """Should validate complete metadata."""
    metadata = ArtifactMetadata(
        version="1.0",
        format_type=ArtifactFormat.LM3Z,
        public_key=bytes(32),
        signature=bytes(64),
    )
    
    is_valid, error = validate_metadata(metadata)
    assert is_valid is True
    assert error is None


def test_validate_metadata_raw_format():
    """Should validate raw format without crypto fields."""
    metadata = ArtifactMetadata(
        version="raw",
        format_type=ArtifactFormat.RIM95,
        public_key=None,
        signature=None,
    )
    
    is_valid, error = validate_metadata(metadata)
    assert is_valid is True  # Raw format doesn't require crypto


# ─── Integration Tests ───────────────────────────────────────────────────────

def test_metadata_parsing_deterministic(sample_lm3z_content):
    """Metadata parsing should be deterministic."""
    result1 = parse_metadata(sample_lm3z_content, "test.lm3z")
    result2 = parse_metadata(sample_lm3z_content, "test.lm3z")
    
    assert result1.success == result2.success
    assert result1.metadata.content_hash == result2.metadata.content_hash
    assert result1.metadata.version == result2.metadata.version


def test_metadata_extraction_does_not_modify_payload(sample_lm3z_content):
    """Payload extraction should not modify content."""
    result = parse_metadata(sample_lm3z_content, "test.lm3z")
    
    # Payload should be the unchanged binary content
    assert result.raw_payload is not None
    assert len(result.raw_payload) == result.metadata.payload_length
