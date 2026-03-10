"""
Strict validation tests for metadata parsing.

Tests for:
- Extra fields → REJECT
- Malformed schema → REJECT
- Unsupported version → REJECT
- Invalid JSON → REJECT
- Hash mismatch → REJECT
"""
import hashlib
import json
import struct
import pytest

from app.services.metadata_parser import parse_metadata
from app.models.metadata_schemas import (
    ArtifactFormat,
    SUPPORTED_LM3Z_VERSIONS,
    SUPPORTED_RIM0_VERSIONS,
    SUPPORTED_RIM95_VERSIONS,
    validate_json_metadata_strict,
    LM3Z_REQUIRED_FIELDS,
    LM3Z_ALLOWED_FIELDS,
    RIM95_REQUIRED_FIELDS,
    RIM95_ALLOWED_FIELDS,
)
from app.services.signature_verification import (
    verify_signature,
    generate_test_keypair,
    sign_payload,
)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def build_lm3z(json_metadata: dict, payload: bytes) -> bytes:
    """Build a valid LM3Z file with given metadata."""
    # Generate a keypair for signing
    private_key, public_key = generate_test_keypair()
    signature = sign_payload(payload, private_key)
    
    json_bytes = json.dumps(json_metadata).encode("utf-8")
    header_size = 108 + len(json_bytes)
    payload_size = len(payload)
    
    # Build header
    data = b"LM3Z"
    data += struct.pack("<I", header_size)
    data += struct.pack("<I", payload_size)
    data += public_key  # 32 bytes
    data += signature   # 64 bytes
    data += json_bytes
    data += payload
    
    return data


def build_rim95(json_metadata: dict, payload: bytes) -> bytes:
    """Build a valid RIM95 file with given metadata."""
    private_key, public_key = generate_test_keypair()
    signature = sign_payload(payload, private_key)
    
    json_bytes = json.dumps(json_metadata).encode("utf-8")
    
    data = b"R95\x00"
    data += struct.pack("<I", len(json_bytes))
    data += public_key  # 32 bytes
    data += signature   # 64 bytes
    data += json_bytes
    data += payload
    
    return data


def build_rim0(version: int, payload: bytes) -> bytes:
    """Build a valid RIM0 file with given version."""
    private_key, public_key = generate_test_keypair()
    signature = sign_payload(payload, private_key)
    
    # RIM0 header = 24 bytes
    # Then key at offset 24, signature at offset 56, payload at 120
    key_offset = 24
    sig_offset = 56
    payload_offset = 120
    payload_size = len(payload)
    
    data = b"RIM0"
    data += struct.pack("<H", version)  # version
    data += struct.pack("<H", 0)        # flags
    data += struct.pack("<I", key_offset)
    data += struct.pack("<I", sig_offset)
    data += struct.pack("<I", payload_offset)
    data += struct.pack("<I", payload_size)
    data += public_key  # at offset 24, 32 bytes
    data += signature   # at offset 56, 64 bytes
    data += payload     # at offset 120
    
    return data


# ─── JSON Metadata Validation Tests ──────────────────────────────────────────

class TestStrictJsonValidation:
    """Tests for validate_json_metadata_strict function."""
    
    def test_valid_metadata_passes(self):
        """Valid metadata with all required fields should pass."""
        data = {"version": "1.0", "artifact_id": "test-123"}
        is_valid, error, parsed = validate_json_metadata_strict(
            data, LM3Z_REQUIRED_FIELDS, LM3Z_ALLOWED_FIELDS, "LM3Z"
        )
        assert is_valid is True
        assert error is None
        assert parsed.version == "1.0"
    
    def test_missing_required_field_fails(self):
        """Missing required field should fail."""
        data = {"artifact_id": "test-123"}  # missing 'version'
        is_valid, error, parsed = validate_json_metadata_strict(
            data, LM3Z_REQUIRED_FIELDS, LM3Z_ALLOWED_FIELDS, "LM3Z"
        )
        assert is_valid is False
        assert "missing required fields" in error.lower()
        assert "version" in error
    
    def test_extra_field_fails(self):
        """Extra unknown field should fail in strict mode."""
        data = {
            "version": "1.0",
            "unknown_field": "should_fail",
            "another_bad_field": 123
        }
        is_valid, error, parsed = validate_json_metadata_strict(
            data, LM3Z_REQUIRED_FIELDS, LM3Z_ALLOWED_FIELDS, "LM3Z"
        )
        assert is_valid is False
        assert "unknown fields" in error.lower()
        assert "unknown_field" in error or "another_bad_field" in error


# ─── LM3Z Strict Parsing Tests ───────────────────────────────────────────────

class TestLm3zStrictParsing:
    """Tests for strict LM3Z parsing."""
    
    def test_extra_json_fields_rejected(self):
        """LM3Z with extra JSON fields should fail in strict mode."""
        payload = b"test payload content"
        metadata = {
            "version": "1.0",
            "extra_field": "should_fail",
            "nested": {"bad": "data"}
        }
        content = build_lm3z(metadata, payload)
        
        result = parse_metadata(content, "test.lm3z", strict=True)
        
        assert result.success is False
        assert result.error_code == "METADATA_SCHEMA_ERROR"
        assert "unknown fields" in result.error_message.lower()
    
    def test_unsupported_version_rejected(self):
        """LM3Z with unsupported version should fail."""
        payload = b"test payload content"
        metadata = {"version": "99.0"}  # Unsupported version
        content = build_lm3z(metadata, payload)
        
        result = parse_metadata(content, "test.lm3z", strict=True)
        
        assert result.success is False
        assert result.error_code == "METADATA_UNSUPPORTED_VERSION"
        assert "99.0" in result.error_message
    
    def test_supported_versions_accepted(self):
        """All supported LM3Z versions should be accepted."""
        payload = b"test payload content"
        
        for version in SUPPORTED_LM3Z_VERSIONS:
            metadata = {"version": version}
            content = build_lm3z(metadata, payload)
            
            result = parse_metadata(content, "test.lm3z", strict=True)
            
            assert result.success is True, f"Version {version} should be accepted"
    
    def test_malformed_json_rejected(self):
        """LM3Z with malformed JSON should fail."""
        # Build content manually with invalid JSON
        private_key, public_key = generate_test_keypair()
        payload = b"test payload"
        signature = sign_payload(payload, private_key)
        
        invalid_json = b"{not valid json"
        header_size = 108 + len(invalid_json)
        
        content = b"LM3Z"
        content += struct.pack("<I", header_size)
        content += struct.pack("<I", len(payload))
        content += public_key
        content += signature
        content += invalid_json
        content += payload
        
        result = parse_metadata(content, "test.lm3z", strict=True)
        
        assert result.success is False
        assert result.error_code == "METADATA_JSON_PARSE_ERROR"
    
    def test_declared_hash_mismatch_rejected(self):
        """LM3Z with incorrect declared hash should fail."""
        payload = b"test payload content"
        wrong_hash = "0" * 64  # Wrong hash
        metadata = {"version": "1.0", "declared_hash": wrong_hash}
        content = build_lm3z(metadata, payload)
        
        result = parse_metadata(content, "test.lm3z", strict=True)
        
        assert result.success is False
        assert result.error_code == "METADATA_HASH_MISMATCH"
    
    def test_declared_hash_correct_accepted(self):
        """LM3Z with correct declared hash should succeed."""
        payload = b"test payload content"
        correct_hash = hashlib.sha256(payload).hexdigest()
        metadata = {"version": "1.0", "declared_hash": correct_hash}
        content = build_lm3z(metadata, payload)
        
        result = parse_metadata(content, "test.lm3z", strict=True)
        
        assert result.success is True
        assert result.metadata.hash_verified is True


# ─── RIM0 Strict Parsing Tests ───────────────────────────────────────────────

class TestRim0StrictParsing:
    """Tests for strict RIM0 parsing."""
    
    def test_unsupported_version_rejected(self):
        """RIM0 with unsupported version should fail."""
        payload = b"test payload content"
        content = build_rim0(version=99, payload=payload)  # Unsupported version
        
        result = parse_metadata(content, "test.rim0", strict=True)
        
        assert result.success is False
        assert result.error_code == "METADATA_UNSUPPORTED_VERSION"
    
    def test_supported_versions_accepted(self):
        """All supported RIM0 versions should be accepted."""
        payload = b"test payload content"
        
        for version in SUPPORTED_RIM0_VERSIONS:
            content = build_rim0(version=version, payload=payload)
            
            result = parse_metadata(content, "test.rim0", strict=True)
            
            assert result.success is True, f"Version {version} should be accepted"


# ─── RIM95 Strict Parsing Tests ──────────────────────────────────────────────

class TestRim95StrictParsing:
    """Tests for strict RIM95 parsing."""
    
    def test_extra_json_fields_rejected(self):
        """RIM95 with extra JSON fields should fail in strict mode."""
        payload = b"test payload content"
        metadata = {
            "version": "95.0",
            "extra_field": "should_fail"
        }
        content = build_rim95(metadata, payload)
        
        result = parse_metadata(content, "test.rim95", strict=True)
        
        assert result.success is False
        assert result.error_code == "METADATA_SCHEMA_ERROR"
    
    def test_unsupported_version_rejected(self):
        """RIM95 with unsupported major version should fail."""
        payload = b"test payload content"
        metadata = {"version": "96.0"}  # Not version 95
        content = build_rim95(metadata, payload)
        
        result = parse_metadata(content, "test.rim95", strict=True)
        
        assert result.success is False
        assert result.error_code == "METADATA_UNSUPPORTED_VERSION"
    
    def test_version_95_accepted(self):
        """RIM95 version 95.x should be accepted."""
        payload = b"test payload content"
        metadata = {"version": "95.0"}
        content = build_rim95(metadata, payload)
        
        result = parse_metadata(content, "test.rim95", strict=True)
        
        assert result.success is True
    
    def test_malformed_json_rejected(self):
        """RIM95 with malformed JSON should fail."""
        private_key, public_key = generate_test_keypair()
        payload = b"test payload"
        signature = sign_payload(payload, private_key)
        
        invalid_json = b"not json at all"
        
        content = b"R95\x00"
        content += struct.pack("<I", len(invalid_json))
        content += public_key
        content += signature
        content += invalid_json
        content += payload
        
        result = parse_metadata(content, "test.rim95", strict=True)
        
        assert result.success is False
        assert result.error_code == "METADATA_JSON_PARSE_ERROR"
    
    def test_declared_hash_mismatch_rejected(self):
        """RIM95 with incorrect declared hash should fail."""
        payload = b"test payload content"
        wrong_hash = "abcd" * 16  # Wrong hash
        metadata = {"version": "95.0", "declared_hash": wrong_hash}
        content = build_rim95(metadata, payload)
        
        result = parse_metadata(content, "test.rim95", strict=True)
        
        assert result.success is False
        assert result.error_code == "METADATA_HASH_MISMATCH"


# ─── Non-Strict Mode Tests ───────────────────────────────────────────────────

class TestNonStrictMode:
    """Tests to verify non-strict mode still works for backward compatibility."""
    
    def test_extra_fields_allowed_nonstrict(self):
        """Extra fields should be allowed in non-strict mode."""
        payload = b"test payload content"
        metadata = {
            "version": "1.0",
            "extra_field": "should_be_allowed"
        }
        content = build_lm3z(metadata, payload)
        
        result = parse_metadata(content, "test.lm3z", strict=False)
        
        # Non-strict mode should succeed despite extra fields
        assert result.success is True
    
    def test_unknown_format_fallback_nonstrict(self):
        """Unknown format should fall back to raw binary in non-strict mode."""
        content = bytes(range(256)) * 4  # No magic bytes
        
        result = parse_metadata(content, "test.xyz", strict=False)
        
        assert result.success is True
        assert result.metadata.version == "raw"


# ─── Edge Cases ──────────────────────────────────────────────────────────────

class TestEdgeCases:
    """Edge case tests for strict validation."""
    
    def test_empty_version_rejected(self):
        """Empty version string should fail validation."""
        payload = b"test payload"
        metadata = {"version": ""}
        content = build_lm3z(metadata, payload)
        
        result = parse_metadata(content, "test.lm3z", strict=True)
        
        assert result.success is False
    
    def test_version_with_extra_decimals_handled(self):
        """Version like '1.0.0' should still work if prefix matches."""
        # For now, we only check if version is in SUPPORTED list
        # '1.0' is supported, but '1.0.0' is not
        payload = b"test payload"
        metadata = {"version": "1.0.0"}
        content = build_lm3z(metadata, payload)
        
        result = parse_metadata(content, "test.lm3z", strict=True)
        
        # This should fail because '1.0.0' is not in SUPPORTED_LM3Z_VERSIONS
        assert result.success is False
        assert result.error_code == "METADATA_UNSUPPORTED_VERSION"
    
    def test_truncated_file_rejected(self):
        """File that declares larger content than available should fail."""
        payload = b"test payload"
        metadata = {"version": "1.0"}
        json_bytes = json.dumps(metadata).encode("utf-8")
        
        # Build header claiming larger payload than we provide
        private_key, public_key = generate_test_keypair()
        signature = sign_payload(payload, private_key)
        
        header_size = 108 + len(json_bytes)
        declared_payload_size = 10000  # Lie about size
        
        content = b"LM3Z"
        content += struct.pack("<I", header_size)
        content += struct.pack("<I", declared_payload_size)
        content += public_key
        content += signature
        content += json_bytes
        content += payload  # Much smaller than declared
        
        result = parse_metadata(content, "test.lm3z", strict=True)
        
        assert result.success is False
        assert "exceeds" in result.error_message.lower()
