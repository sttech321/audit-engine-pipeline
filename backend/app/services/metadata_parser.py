"""
Metadata parsing service for .lm3z, .rim0, and .rim95 audit artifact formats.

STRICT IMPLEMENTATION:
- No fallback logic
- No silent error handling
- Rejects unknown fields
- Validates required fields
- Validates version compatibility

If parsing fails, it fails FAST with a structured error.
"""
import hashlib
import json
import struct
from typing import Optional, Tuple

from app.logging_config import logger
from app.models.metadata_schemas import (
    ArtifactFormat,
    ArtifactMetadata,
    MetadataParseResult,
    SUPPORTED_LM3Z_VERSIONS,
    SUPPORTED_RIM0_VERSIONS,
    SUPPORTED_RIM95_VERSIONS,
    LM3Z_REQUIRED_FIELDS,
    LM3Z_ALLOWED_FIELDS,
    RIM95_REQUIRED_FIELDS,
    RIM95_ALLOWED_FIELDS,
    validate_json_metadata_strict,
)


# ─── Format Magic Bytes ──────────────────────────────────────────────────────

LM3Z_MAGIC = b"LM3Z"
RIM0_MAGIC = b"RIM0"
RIM95_MAGIC = b"R95\x00"

# Minimum header sizes
LM3Z_MIN_HEADER = 64
RIM0_MIN_HEADER = 48
RIM95_MIN_HEADER = 32


def detect_format(contents: bytes, filename: str) -> ArtifactFormat:
    """
    Detect artifact format from magic bytes ONLY.
    
    STRICT: Extension-based fallback is NOT used for format detection.
    Files MUST have correct magic bytes.
    
    Args:
        contents: Raw file contents
        filename: Original filename (used only for logging)
        
    Returns:
        Detected ArtifactFormat (UNKNOWN if magic bytes don't match)
    """
    if len(contents) < 4:
        return ArtifactFormat.UNKNOWN
    
    magic = contents[:4]
    if magic == LM3Z_MAGIC:
        return ArtifactFormat.LM3Z
    if magic == RIM0_MAGIC:
        return ArtifactFormat.RIM0
    
    if magic == RIM95_MAGIC:
        return ArtifactFormat.RIM95
    
    return ArtifactFormat.UNKNOWN


def parse_metadata(contents: bytes, filename: str, strict: bool = True) -> MetadataParseResult:
    """
    Parse metadata from audit artifact file.
    
    STRICT MODE (default):
    - Requires valid magic bytes
    - Rejects unknown JSON fields
    - Validates version compatibility
    - Fails on any parse error
    
    NON-STRICT MODE (legacy compatibility):
    - Falls back to raw binary parsing for unknown formats
    - Allows JSON parse failures with defaults
    
    Args:
        contents: Raw file contents
        filename: Original filename
        strict: Enable strict validation (default: True)
        
    Returns:
        MetadataParseResult with parsed metadata or error details
    """
    try:
        format_type = detect_format(contents, filename)
        
        if format_type == ArtifactFormat.LM3Z:
            return _parse_lm3z(contents, filename, strict=strict)
        elif format_type == ArtifactFormat.RIM0:
            return _parse_rim0(contents, filename, strict=strict)
        elif format_type == ArtifactFormat.RIM95:
            return _parse_rim95(contents, filename, strict=strict)
        else:
            # Unknown format
            if strict:
                return MetadataParseResult(
                    success=False,
                    error_code="METADATA_UNKNOWN_FORMAT",
                    error_message=f"Unknown artifact format: magic bytes {contents[:4].hex() if len (contents) >= 4 else 'missing'}"
                )
            else:
                # Non-strict: treat as raw binary (backward compatible)
                return _parse_raw_binary(contents, filename)
            
    except Exception as e:
        logger.error(f"Metadata parsing error for {filename}: {e}")
        return MetadataParseResult(
            success=False,
            error_code="METADATA_PARSE_ERROR",
            error_message=f"Failed to parse metadata: {str(e)}"
        )


def _parse_lm3z(contents: bytes, filename: str, strict: bool = True) -> MetadataParseResult:
    """
    Parse .lm3z format (JSON-based with binary payload).
    
    LM3Z Format Structure:
    - Bytes 0-3: Magic "LM3Z"
    - Bytes 4-7: Header size (uint32 LE)
    - Bytes 8-11: Payload size (uint32 LE)
    - Bytes 12-43: Public key (32 bytes)
    - Bytes 44-107: Signature (64 bytes)
    - Bytes 108-header_size: JSON metadata
    - Remaining: Binary payload
    
    STRICT MODE:
    - JSON metadata MUST parse successfully
    - Unknown fields are rejected
    - Version must be in SUPPORTED_LM3Z_VERSIONS
    """
    if len(contents) < LM3Z_MIN_HEADER:
        return MetadataParseResult(
            success=False,
            error_code="METADATA_INVALID_FORMAT",
            error_message=f"LM3Z file too small: {len(contents)} bytes (minimum {LM3Z_MIN_HEADER})"
        )
    
    # Verify magic
    if contents[:4] != LM3Z_MAGIC:
        return MetadataParseResult(
            success=False,
            error_code="METADATA_INVALID_FORMAT",
            error_message="Invalid LM3Z magic bytes"
        )
    
    try:
        # Parse header
        header_size = struct.unpack("<I", contents[4:8])[0]
        payload_size = struct.unpack("<I", contents[8:12])[0]
        
        if header_size > len(contents):
            return MetadataParseResult(
                success=False,
                error_code="METADATA_INVALID_FORMAT",
                error_message=f"Invalid header size: {header_size} exceeds file size {len(contents)}"
            )
        
        # Extract cryptographic fields
        public_key = contents[12:44]
        signature = contents[44:108]
        
        # Validate key/signature sizes
        if len(public_key) != 32:
            return MetadataParseResult(
                success=False,
                error_code="METADATA_INVALID_FORMAT",
                error_message=f"Invalid public key size: {len(public_key)} bytes (expected 32)"
            )
        if len(signature) != 64:
            return MetadataParseResult(
                success=False,
                error_code="METADATA_INVALID_FORMAT",
                error_message=f"Invalid signature size: {len(signature)} bytes (expected 64)"
            )
        
        # Parse JSON metadata - STRICT: must succeed
        json_start = 108
        json_end = header_size
        json_bytes = contents[json_start:json_end]
        
        if not json_bytes:
            return MetadataParseResult(
                success=False,
                error_code="METADATA_INVALID_FORMAT",
                error_message="LM3Z file missing JSON metadata block"
            )
        
        try:
            metadata_dict = json.loads(json_bytes.decode("utf-8"))
        except json.JSONDecodeError as e:
            return MetadataParseResult(
                success=False,
                error_code="METADATA_JSON_PARSE_ERROR",
                error_message=f"Failed to parse LM3Z JSON metadata: {e}"
            )
        except UnicodeDecodeError as e:
            return MetadataParseResult(
                success=False,
                error_code="METADATA_ENCODING_ERROR",
                error_message=f"Invalid UTF-8 encoding in LM3Z metadata: {e}"
            )
        
        # STRICT: Validate JSON fields
        if strict:
            is_valid, error_msg, _ = validate_json_metadata_strict(
                metadata_dict, LM3Z_REQUIRED_FIELDS, LM3Z_ALLOWED_FIELDS, "LM3Z"
            )
            if not is_valid:
                return MetadataParseResult(
                    success=False,
                    error_code="METADATA_SCHEMA_ERROR",
                    error_message=error_msg
                )
            
            # Validate version
            version = metadata_dict.get("version", "")
            if version not in SUPPORTED_LM3Z_VERSIONS:
                return MetadataParseResult(
                    success=False,
                    error_code="METADATA_UNSUPPORTED_VERSION",
                    error_message=f"Unsupported LM3Z version: {version}. Supported: {', '.join(sorted(SUPPORTED_LM3Z_VERSIONS))}"
                )
        
        # Calculate content hash for verification
        payload_start = header_size
        payload_end = header_size + payload_size
        
        if payload_end > len(contents):
            return MetadataParseResult(
                success=False,
                error_code="METADATA_INVALID_FORMAT",
                error_message=f"Declared payload size {payload_size} exceeds available data"
            )
        
        payload = contents[payload_start:payload_end]
        content_hash = hashlib.sha256(payload).hexdigest()
        
        # Check declared hash if present
        declared_hash = metadata_dict.get("declared_hash")
        hash_verified = False
        if declared_hash:
            if declared_hash != content_hash:
                return MetadataParseResult(
                    success=False,
                    error_code="METADATA_HASH_MISMATCH",
                    error_message=f"Declared hash mismatch: expected {declared_hash}, computed {content_hash}"
                )
            hash_verified = True
        
        metadata = ArtifactMetadata(
            version=metadata_dict.get("version", "1.0"),
            format_type=ArtifactFormat.LM3Z,
            public_key=public_key,
            signature=signature,
            artifact_id=metadata_dict.get("artifact_id"),
            created_at=metadata_dict.get("created_at"),
            content_hash=content_hash,
            declared_hash=declared_hash,
            author=metadata_dict.get("author"),
            description=metadata_dict.get("description"),
            tags=metadata_dict.get("tags", []),
            payload_offset=payload_start,
            payload_length=len(payload),
            hash_verified=hash_verified
        )
        
        return MetadataParseResult(
            success=True,
            metadata=metadata,
            raw_payload=payload
        )
        
    except struct.error as e:
        return MetadataParseResult(
            success=False,
            error_code="METADATA_INVALID_FORMAT",
            error_message=f"Failed to parse LM3Z header: {e}"
        )


def _parse_rim0(contents: bytes, filename: str, strict: bool = True) -> MetadataParseResult:
    """
    Parse .rim0 format (binary format).
    
    RIM0 Format Structure:
    - Bytes 0-3: Magic "RIM0"
    - Bytes 4-5: Version (uint16 LE)
    - Bytes 6-7: Flags (uint16 LE)
    - Bytes 8-11: Key offset (uint32 LE)
    - Bytes 12-15: Signature offset (uint32 LE)
    - Bytes 16-19: Payload offset (uint32 LE)
    - Bytes 20-23: Payload size (uint32 LE)
    - Variable: Public key (32 bytes at key_offset)
    - Variable: Signature (64 bytes at sig_offset)
    - Variable: Payload (at payload_offset)
    
    STRICT MODE:
    - Version must be in SUPPORTED_RIM0_VERSIONS
    - Key and signature offsets must be valid
    - Payload must fit within file bounds
    """
    if len(contents) < RIM0_MIN_HEADER:
        return MetadataParseResult(
            success=False,
            error_code="METADATA_INVALID_FORMAT",
            error_message=f"RIM0 file too small: {len(contents)} bytes (minimum {RIM0_MIN_HEADER})"
        )
    
    # Verify magic
    if contents[:4] != RIM0_MAGIC:
        return MetadataParseResult(
            success=False,
            error_code="METADATA_INVALID_FORMAT",
            error_message="Invalid RIM0 magic bytes"
        )
    
    try:
        # Parse header
        version = struct.unpack("<H", contents[4:6])[0]
        flags = struct.unpack("<H", contents[6:8])[0]
        key_offset = struct.unpack("<I", contents[8:12])[0]
        sig_offset = struct.unpack("<I", contents[12:16])[0]
        payload_offset = struct.unpack("<I", contents[16:20])[0]
        payload_size = struct.unpack("<I", contents[20:24])[0]
        
        # STRICT: Validate version
        if strict and version not in SUPPORTED_RIM0_VERSIONS:
            return MetadataParseResult(
                success=False,
                error_code="METADATA_UNSUPPORTED_VERSION",
                error_message=f"Unsupported RIM0 version: {version}. Supported: {', '.join(map(str, sorted(SUPPORTED_RIM0_VERSIONS)))}"
            )
        
        # STRICT: Validate offsets
        if strict:
            if key_offset == 0:
                return MetadataParseResult(
                    success=False,
                    error_code="METADATA_INVALID_FORMAT",
                    error_message="RIM0 key_offset cannot be 0"
                )
            if sig_offset == 0:
                return MetadataParseResult(
                    success=False,
                    error_code="METADATA_INVALID_FORMAT",
                    error_message="RIM0 sig_offset cannot be 0"
                )
        
        # Extract public key
        if key_offset + 32 > len(contents):
            return MetadataParseResult(
                success=False,
                error_code="METADATA_INVALID_FORMAT",
                error_message=f"Key offset {key_offset} + 32 exceeds file size {len(contents)}"
            )
        public_key = contents[key_offset:key_offset + 32]
        
        # Extract signature
        if sig_offset + 64 > len(contents):
            return MetadataParseResult(
                success=False,
                error_code="METADATA_INVALID_FORMAT",
                error_message=f"Signature offset {sig_offset} + 64 exceeds file size {len(contents)}"
            )
        signature = contents[sig_offset:sig_offset + 64]
        
        # Extract payload
        if payload_offset >= len(contents):
            return MetadataParseResult(
                success=False,
                error_code="METADATA_INVALID_FORMAT",
                error_message=f"Payload offset {payload_offset} exceeds file size {len(contents)}"
            )
        
        payload_end = payload_offset + payload_size
        if strict and payload_end > len(contents):
            return MetadataParseResult(
                success=False,
                error_code="METADATA_INVALID_FORMAT",
                error_message=f"Declared payload size {payload_size} exceeds available data"
            )
        
        payload = contents[payload_offset:payload_end]
        
        # Calculate content hash
        content_hash = hashlib.sha256(payload).hexdigest()
        
        metadata = ArtifactMetadata(
            version=f"{version}.0",
            format_type=ArtifactFormat.RIM0,
            public_key=public_key,
            signature=signature,
            content_hash=content_hash,
            payload_offset=payload_offset,
            payload_length=len(payload)
        )
        
        return MetadataParseResult(
            success=True,
            metadata=metadata,
            raw_payload=payload
        )
        
    except struct.error as e:
        return MetadataParseResult(
            success=False,
            error_code="METADATA_INVALID_FORMAT",
            error_message=f"Failed to parse RIM0 header: {e}"
        )


def _parse_rim95(contents: bytes, filename: str, strict: bool = True) -> MetadataParseResult:
    """
    Parse .rim95 format (hybrid JSON + binary).
    
    RIM95 Format Structure:
    - Bytes 0-3: Magic "R95\\x00"
    - Bytes 4-7: JSON metadata size (uint32 LE)
    - Bytes 8-39: Public key (32 bytes)
    - Bytes 40-103: Signature (64 bytes)
    - Bytes 104-(104+json_size): JSON metadata
    - Remaining: Binary payload
    
    STRICT MODE:
    - Requires valid magic bytes (no backward compatibility fallback)
    - JSON metadata MUST parse successfully
    - Unknown fields are rejected
    - Version must be in SUPPORTED_RIM95_VERSIONS
    """
    if len(contents) < RIM95_MIN_HEADER:
        return MetadataParseResult(
            success=False,
            error_code="METADATA_INVALID_FORMAT",
            error_message=f"RIM95 file too small: {len(contents)} bytes (minimum {RIM95_MIN_HEADER})"
        )
    
    # Verify magic - STRICT: no fallback
    if contents[:4] != RIM95_MAGIC:
        return MetadataParseResult(
            success=False,
            error_code="METADATA_INVALID_FORMAT",
            error_message=f"Invalid RIM95 magic bytes: expected 'R95\\x00', got {contents[:4]!r}"
        )
    
    try:
        # Parse header
        json_size = struct.unpack("<I", contents[4:8])[0]
        
        # Extract cryptographic fields
        public_key = contents[8:40]
        signature = contents[40:104]
        
        # Validate key/signature sizes
        if len(public_key) != 32:
            return MetadataParseResult(
                success=False,
                error_code="METADATA_INVALID_FORMAT",
                error_message=f"Invalid public key size: {len(public_key)} bytes (expected 32)"
            )
        if len(signature) != 64:
            return MetadataParseResult(
                success=False,
                error_code="METADATA_INVALID_FORMAT",
                error_message=f"Invalid signature size: {len(signature)} bytes (expected 64)"
            )
        
        # Parse JSON metadata - STRICT: must succeed
        json_start = 104
        json_end = 104 + json_size
        
        if json_size == 0:
            return MetadataParseResult(
                success=False,
                error_code="METADATA_INVALID_FORMAT",
                error_message="RIM95 file has zero-length JSON metadata"
            )
        
        if json_end > len(contents):
            return MetadataParseResult(
                success=False,
                error_code="METADATA_INVALID_FORMAT",
                error_message=f"JSON metadata size {json_size} exceeds available data"
            )
        
        json_bytes = contents[json_start:json_end]
        
        try:
            metadata_dict = json.loads(json_bytes.decode("utf-8"))
        except json.JSONDecodeError as e:
            return MetadataParseResult(
                success=False,
                error_code="METADATA_JSON_PARSE_ERROR",
                error_message=f"Failed to parse RIM95 JSON metadata: {e}"
            )
        except UnicodeDecodeError as e:
            return MetadataParseResult(
                success=False,
                error_code="METADATA_ENCODING_ERROR",
                error_message=f"Invalid UTF-8 encoding in RIM95 metadata: {e}"
            )
        
        # STRICT: Validate JSON fields
        if strict:
            is_valid, error_msg, _ = validate_json_metadata_strict(
                metadata_dict, RIM95_REQUIRED_FIELDS, RIM95_ALLOWED_FIELDS, "RIM95"
            )
            if not is_valid:
                return MetadataParseResult(
                    success=False,
                    error_code="METADATA_SCHEMA_ERROR",
                    error_message=error_msg
                )
            
            # Validate version (extract major version from string like "95.0")
            version_str = metadata_dict.get("version", "")
            try:
                major_version = int(version_str.split(".")[0])
            except (ValueError, IndexError):
                return MetadataParseResult(
                    success=False,
                    error_code="METADATA_INVALID_VERSION",
                    error_message=f"Invalid RIM95 version format: {version_str}"
                )
            
            if major_version not in SUPPORTED_RIM95_VERSIONS:
                return MetadataParseResult(
                    success=False,
                    error_code="METADATA_UNSUPPORTED_VERSION",
                    error_message=f"Unsupported RIM95 version: {major_version}. Supported: {', '.join(map(str, sorted(SUPPORTED_RIM95_VERSIONS)))}"
                )
        
        # Extract payload
        payload_offset = json_end
        payload = contents[payload_offset:]
        
        # Calculate content hash
        content_hash = hashlib.sha256(payload).hexdigest()
        
        # Check declared hash if present
        declared_hash = metadata_dict.get("declared_hash")
        hash_verified = False
        if declared_hash:
            if declared_hash != content_hash:
                return MetadataParseResult(
                    success=False,
                    error_code="METADATA_HASH_MISMATCH",
                    error_message=f"Declared hash mismatch: expected {declared_hash}, computed {content_hash}"
                )
            hash_verified = True
        
        metadata = ArtifactMetadata(
            version=metadata_dict.get("version", "95.0"),
            format_type=ArtifactFormat.RIM95,
            public_key=public_key,
            signature=signature,
            artifact_id=metadata_dict.get("artifact_id"),
            created_at=metadata_dict.get("created_at"),
            content_hash=content_hash,
            declared_hash=declared_hash,
            author=metadata_dict.get("author"),
            description=metadata_dict.get("description"),
            tags=metadata_dict.get("tags", []),
            payload_offset=payload_offset,
            payload_length=len(payload),
            hash_verified=hash_verified
        )
        
        return MetadataParseResult(
            success=True,
            metadata=metadata,
            raw_payload=payload
        )
        
    except struct.error as e:
        return MetadataParseResult(
            success=False,
            error_code="METADATA_INVALID_FORMAT",
            error_message=f"Failed to parse RIM95 header: {e}"
        )


def _parse_raw_binary(contents: bytes, filename: str) -> MetadataParseResult:
    """
    Parse raw binary files (backward compatibility mode).
    
    This allows the existing pipeline to process files that don't have
    structured metadata headers. No signature verification is possible
    for these files.
    """
    content_hash = hashlib.sha256(contents).hexdigest()
    
    # Determine format from extension for metadata
    format_type = ArtifactFormat.UNKNOWN
    lower_name = filename.lower()
    if lower_name.endswith(".lm3z"):
        format_type = ArtifactFormat.LM3Z
    elif lower_name.endswith(".rim0"):
        format_type = ArtifactFormat.RIM0
    elif lower_name.endswith(".rim95"):
        format_type = ArtifactFormat.RIM95
    
    metadata = ArtifactMetadata(
        version="raw",
        format_type=format_type,
        public_key=None,
        signature=None,
        content_hash=content_hash,
        payload_offset=0,
        payload_length=len(contents)
    )
    
    return MetadataParseResult(
        success=True,
        metadata=metadata,
        raw_payload=contents
    )


def validate_metadata(metadata: ArtifactMetadata) -> Tuple[bool, Optional[str]]:
    """
    Validate parsed metadata for completeness and correctness.
    
    Args:
        metadata: Parsed artifact metadata
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check for required cryptographic fields if format supports them
    if metadata.format_type in (ArtifactFormat.LM3Z, ArtifactFormat.RIM0, ArtifactFormat.RIM95):
        if metadata.public_key is None and metadata.version != "raw":
            return False, "Missing public key for signed format"
        if metadata.signature is None and metadata.version != "raw":
            return False, "Missing signature for signed format"
    
    return True, None
