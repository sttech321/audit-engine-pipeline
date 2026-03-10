"""
Structured error schemas for API responses.
These wrap existing errors without changing HTTP status codes or breaking API contracts.
"""
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class ErrorCode(str, Enum):
    """Structured error codes for API responses."""
    # File validation errors
    FILE_EMPTY = "FILE_EMPTY"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    FILE_TOO_SMALL = "FILE_TOO_SMALL"
    FILE_INVALID_TYPE = "FILE_INVALID_TYPE"
    FILE_INVALID_EXTENSION = "FILE_INVALID_EXTENSION"
    FILE_INVALID_MIME = "FILE_INVALID_MIME"
    
    # Metadata parsing errors
    METADATA_PARSE_ERROR = "METADATA_PARSE_ERROR"
    METADATA_INVALID_FORMAT = "METADATA_INVALID_FORMAT"
    METADATA_MISSING_FIELD = "METADATA_MISSING_FIELD"
    METADATA_INVALID_VERSION = "METADATA_INVALID_VERSION"
    
    # Signature verification errors
    SIGNATURE_MISSING = "SIGNATURE_MISSING"
    SIGNATURE_INVALID = "SIGNATURE_INVALID"
    SIGNATURE_PUBLIC_KEY_MISSING = "SIGNATURE_PUBLIC_KEY_MISSING"
    SIGNATURE_VERIFICATION_FAILED = "SIGNATURE_VERIFICATION_FAILED"
    
    # Pipeline errors
    PIPELINE_ERROR = "PIPELINE_ERROR"
    PIPELINE_STAGE_FAILED = "PIPELINE_STAGE_FAILED"
    
    # Rate limiting errors
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    
    # Deduplication errors
    DUPLICATE_UPLOAD = "DUPLICATE_UPLOAD"
    REPLAY_DETECTED = "REPLAY_DETECTED"
    
    # Generic errors
    INTERNAL_ERROR = "INTERNAL_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"


class StructuredError(BaseModel):
    """
    Structured error envelope that wraps error details.
    This is used internally and converted to HTTPException for API responses.
    """
    code: ErrorCode = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[dict[str, Any]] = Field(None, description="Additional error context")
    
    def to_detail(self) -> dict[str, Any]:
        """Convert to HTTPException detail format."""
        return {
            "error": {
                "code": self.code.value,
                "message": self.message,
                "details": self.details or {}
            }
        }


class ValidationError(BaseModel):
    """Validation error with field-level details."""
    field: str = Field(..., description="Field that failed validation")
    message: str = Field(..., description="Validation error message")
    value: Optional[Any] = Field(None, description="Invalid value (sanitized)")


class StructuredErrorResponse(BaseModel):
    """
    Full structured error response envelope.
    Maintains backward compatibility by including 'detail' field.
    """
    detail: str = Field(..., description="Legacy detail message (backward compatible)")
    error: Optional[StructuredError] = Field(None, description="Structured error details")
