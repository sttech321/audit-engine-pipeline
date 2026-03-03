"""
Metadata schemas for .lm3z, .rim0, and .rim95 audit artifact formats.
Strict validation - no extra fields, required fields enforced, versions validated.
"""
from enum import Enum
from typing import Any, Optional, Set

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ArtifactFormat(str, Enum):
    """Supported audit artifact formats."""
    LM3Z = "lm3z"
    RIM0 = "rim0"
    RIM95 = "rim95"
    UNKNOWN = "unknown"


# ─── Supported Versions ──────────────────────────────────────────────────────

SUPPORTED_LM3Z_VERSIONS = {"1.0", "1.1", "2.0"}
SUPPORTED_RIM0_VERSIONS = {1, 2, 3}
SUPPORTED_RIM95_VERSIONS = {95}

# ─── Required/Allowed Fields for JSON Metadata ───────────────────────────────

LM3Z_REQUIRED_FIELDS = {"version"}
LM3Z_ALLOWED_FIELDS = {"version", "artifact_id", "created_at", "author", "description", "tags", "declared_hash"}

RIM95_REQUIRED_FIELDS = {"version"}
RIM95_ALLOWED_FIELDS = {"version", "artifact_id", "created_at", "author", "description", "tags", "declared_hash"}


class StrictJsonMetadata(BaseModel):
    """
    Strict JSON metadata model for LM3Z and RIM95 formats.
    Rejects extra fields and validates required fields.
    """
    model_config = ConfigDict(extra="forbid")  # Reject extra fields
    
    version: str = Field(..., description="Format version")
    artifact_id: Optional[str] = Field(None, description="Unique artifact identifier")
    created_at: Optional[str] = Field(None, description="ISO 8601 creation timestamp")
    author: Optional[str] = Field(None, description="Artifact author/creator")
    description: Optional[str] = Field(None, description="Artifact description")
    tags: Optional[list[str]] = Field(default_factory=list, description="Artifact tags/labels")
    declared_hash: Optional[str] = Field(None, description="Declared SHA-256 hash of payload")
    
    @field_validator("version")
    @classmethod
    def validate_version_format(cls, v: str) -> str:
        """Validate version string format."""
        if not v or not isinstance(v, str):
            raise ValueError("Version must be a non-empty string")
        # Version should match pattern like "1.0", "2.0", "95.0"
        parts = v.split(".")
        if len(parts) < 1 or len(parts) > 3:
            raise ValueError(f"Invalid version format: {v}")
        return v
    
    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: Optional[list]) -> list:
        """Validate tags list."""
        if v is None:
            return []
        if not isinstance(v, list):
            raise ValueError("Tags must be a list")
        for tag in v:
            if not isinstance(tag, str):
                raise ValueError("All tags must be strings")
        return v


class ArtifactMetadata(BaseModel):
    """
    Parsed metadata from audit artifact files.
    
    This model represents the structured metadata extracted from .lm3z, .rim0, and .rim95 files.
    The metadata is used to enrich the audit pipeline context and enable cryptographic verification.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    # Required fields
    version: str = Field(..., description="Artifact format version (e.g., '1.0', '95.0')")
    format_type: ArtifactFormat = Field(..., description="Detected artifact format")
    
    # Cryptographic fields (required for signature verification)
    public_key: Optional[bytes] = Field(None, description="Ed25519 public key (32 bytes)")
    signature: Optional[bytes] = Field(None, description="Ed25519 signature (64 bytes)")
    
    # Artifact identification
    artifact_id: Optional[str] = Field(None, description="Unique artifact identifier")
    created_at: Optional[str] = Field(None, description="ISO 8601 creation timestamp")
    
    # Content hash for signature verification
    content_hash: Optional[str] = Field(None, description="SHA-256 hash of the signed content")
    declared_hash: Optional[str] = Field(None, description="Hash declared in metadata (for comparison)")
    
    # Optional metadata fields
    author: Optional[str] = Field(None, description="Artifact author/creator")
    description: Optional[str] = Field(None, description="Artifact description")
    tags: Optional[list[str]] = Field(default_factory=list, description="Artifact tags/labels")
    
    # Raw content (payload) - for pipeline processing
    payload_offset: int = Field(0, description="Byte offset where payload begins")
    payload_length: int = Field(0, description="Length of payload in bytes")
    
    # Validation flags
    hash_verified: bool = Field(False, description="Whether declared hash matches computed hash")


class MetadataParseResult(BaseModel):
    """Result of metadata parsing operation."""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    success: bool = Field(..., description="Whether parsing succeeded")
    metadata: Optional[ArtifactMetadata] = Field(None, description="Parsed metadata if successful")
    error_code: Optional[str] = Field(None, description="Error code if parsing failed")
    error_message: Optional[str] = Field(None, description="Human-readable error message")
    raw_payload: Optional[bytes] = Field(None, description="Extracted payload for pipeline processing")


def validate_json_metadata_strict(
    data: dict,
    required_fields: Set[str],
    allowed_fields: Set[str],
    format_name: str
) -> tuple[bool, Optional[str], Optional[StrictJsonMetadata]]:
    """
    Strictly validate JSON metadata.
    
    Args:
        data: Parsed JSON dictionary
        required_fields: Set of required field names
        allowed_fields: Set of allowed field names
        format_name: Format name for error messages
        
    Returns:
        Tuple of (is_valid, error_message, parsed_metadata)
    """
    # Check for missing required fields
    missing = required_fields - set(data.keys())
    if missing:
        return False, f"{format_name} metadata missing required fields: {', '.join(sorted(missing))}", None
    
    # Check for extra fields (strict mode)
    extra = set(data.keys()) - allowed_fields
    if extra:
        return False, f"{format_name} metadata contains unknown fields: {', '.join(sorted(extra))}", None
    
    # Parse with strict Pydantic model
    try:
        parsed = StrictJsonMetadata(**data)
        return True, None, parsed
    except Exception as e:
        return False, f"{format_name} metadata validation failed: {str(e)}", None


# ─── LM3Z Format Specifics ───────────────────────────────────────────────────

class Lm3zHeader(BaseModel):
    """Header structure for .lm3z files (JSON-based format)."""
    magic: str = Field(..., description="Magic bytes 'LM3Z'")
    version: str = Field(..., description="Format version")
    header_size: int = Field(..., description="Header size in bytes")
    payload_size: int = Field(..., description="Payload size in bytes")
    

# ─── RIM0 Format Specifics ───────────────────────────────────────────────────

class Rim0Header(BaseModel):
    """Header structure for .rim0 files (binary format)."""
    magic: bytes = Field(..., description="Magic bytes 'RIM0'")
    version: int = Field(..., description="Format version number")
    flags: int = Field(..., description="Format flags")
    key_offset: int = Field(..., description="Offset to public key")
    sig_offset: int = Field(..., description="Offset to signature")
    payload_offset: int = Field(..., description="Offset to payload")


# ─── RIM95 Format Specifics ──────────────────────────────────────────────────

class Rim95Header(BaseModel):
    """Header structure for .rim95 files (hybrid format)."""
    magic: bytes = Field(..., description="Magic bytes 'R95\\x00'")
    version: int = Field(..., description="Format version (95)")
    json_metadata_size: int = Field(..., description="Size of JSON metadata block")
    payload_offset: int = Field(..., description="Offset to binary payload")
