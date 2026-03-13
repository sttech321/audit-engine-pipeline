"""
File validation service with secure file handling.

This is an ADDITIVE service that provides:
- Streaming file upload with SpooledTemporaryFile
- Extension validation for PASS97-supported formats
- MIME type validation
- Size validation (preserves existing error behavior)

NOTE:
- PASS97 upload endpoints enforce supported extensions:
  .lm3z, .rim0, .rim95, .safetensors, .bin, .gguf, .pt, .pth, .ckpt, .onnx.
"""
import hashlib
import io
import tempfile
from typing import Optional, Tuple

from fastapi import UploadFile

from app.config import get_settings
from app.logging_config import logger
from app.models.error_schemas import ErrorCode, StructuredError


# ─── File Types ───────────────────────────────────────────────────────────────

# Extensions supported by PASS97 upload endpoints.
SUPPORTED_EXTENSIONS = {
    ".lm3z",
    ".rim0",
    ".rim95",
    ".safetensors",
    ".bin",
    ".gguf",
    ".pt",
    ".pth",
    ".ckpt",
    ".onnx",
}

# MIME types that may be reported for binary audit artifacts
ALLOWED_MIME_TYPES = {
    "application/octet-stream",
    "application/x-binary",
    "application/binary",
    "application/x-lm3z",
    "application/x-rim0",
    "application/x-rim95",
    "application/x-safetensors",
    "application/x-gguf",
    "application/gguf",
    "application/x-pt",
    "application/x-pytorch",
    "application/x-pth",
    "application/x-ckpt",
    "application/x-onnx",
    "application/onnx",
    # Some systems report these for binary files
    "application/unknown",
    None,  # Allow when MIME type is not detected
    "",    # Allow empty MIME type
}

# Maximum in-memory file size before spooling to disk (1MB)
SPOOL_MAX_SIZE = 1 * 1024 * 1024

settings = get_settings()


class FileValidationResult:
    """Result of file validation."""
    
    def __init__(
        self,
        valid: bool,
        contents: Optional[bytes] = None,
        file_size: int = 0,
        error: Optional[StructuredError] = None
    ):
        self.valid = valid
        self.contents = contents
        self.file_size = file_size
        self.error = error


def get_file_extension(filename: str) -> str:
    """Extract file extension from filename (lowercase, includes leading dot).

    Returns empty string when no extension is present.
    """
    if not filename:
        return ""
    if "." not in filename:
        return ""
    return "." + filename.rsplit(".", 1)[-1].lower()


def validate_file_extension(filename: str) -> Tuple[bool, Optional[StructuredError]]:
    """
    Validate file extension against the PASS97-supported set.
    
    Args:
        filename: Original filename
        
    Returns:
        Tuple of (is_valid, error if invalid)
    """
    ext = get_file_extension(filename)
    if ext not in SUPPORTED_EXTENSIONS:
        return False, StructuredError(
            code=ErrorCode.FILE_INVALID_EXTENSION,
            message=(
                "Invalid file extension. Supported formats: .lm3z, .rim0, .rim95, "
                ".safetensors, .bin, .gguf, .pt, .pth, .ckpt, .onnx."
            ),
            details={"extension": ext or "(none)"},
        )
    return True, None


def validate_mime_type(content_type: Optional[str]) -> Tuple[bool, Optional[StructuredError]]:
    """
    Validate MIME type.
    
    Args:
        content_type: MIME type from upload
        
    Returns:
        Tuple of (is_valid, error if invalid)
    """
    # Normalize content type
    mime = content_type.lower().strip() if content_type else None
    
    # Extract base MIME type (without parameters)
    if mime and ";" in mime:
        mime = mime.split(";")[0].strip()
    
    if mime not in ALLOWED_MIME_TYPES and mime is not None:
        return False, StructuredError(
            code=ErrorCode.FILE_INVALID_MIME,
            message=f"Invalid MIME type: '{mime}'. Binary audit artifacts expected.",
            details={"mime_type": mime}
        )
    return True, None


async def read_file_streaming(
    file: UploadFile,
    max_size: int = None
) -> FileValidationResult:
    """
    Read uploaded file using memory-efficient streaming.
    
    Uses SpooledTemporaryFile to avoid loading very large files entirely into RAM.
    Preserves existing error behavior for size checks.
    
    Args:
        file: FastAPI UploadFile
        max_size: Maximum allowed size (defaults to settings.max_file_size)
        
    Returns:
        FileValidationResult with contents or error
    """
    if max_size is None:
        max_size = settings.max_file_size
    
    try:
        # Use SpooledTemporaryFile for memory-efficient reading
        # Files smaller than SPOOL_MAX_SIZE stay in memory
        # Larger files are written to a temporary file
        with tempfile.SpooledTemporaryFile(max_size=SPOOL_MAX_SIZE) as spooled:
            total_size = 0
            chunk_size = 1 * 1024 * 1024  # 1 MiB chunks (PASS97 spec compliant)
            
            while True:
                chunk = await file.read(chunk_size)
                if not chunk:
                    break
                
                total_size += len(chunk)
                
                # Check size during streaming to fail fast
                if total_size > max_size:
                    return FileValidationResult(
                        valid=False,
                        file_size=total_size,
                        error=StructuredError(
                            code=ErrorCode.FILE_TOO_LARGE,
                            message=f"File too large. Maximum size is {max_size // 1_000_000}MB.",
                            details={"size": total_size, "max_size": max_size}
                        )
                    )
                
                spooled.write(chunk)
            
            # Read back the contents
            spooled.seek(0)
            contents = spooled.read()
            
            return FileValidationResult(
                valid=True,
                contents=contents,
                file_size=total_size
            )
            
    except Exception as e:
        logger.error(f"Error reading file: {e}")
        return FileValidationResult(
            valid=False,
            error=StructuredError(
                code=ErrorCode.INTERNAL_ERROR,
                message="Failed to read uploaded file",
                details={"error": str(e)}
            )
        )


def validate_file_size(contents: bytes) -> Tuple[bool, Optional[StructuredError]]:
    """
    Validate file size.
    
    This preserves the existing size check behavior.
    
    Args:
        contents: File contents
        
    Returns:
        Tuple of (is_valid, error if invalid)
    """
    file_size = len(contents)
    
    # Empty file check (matches existing 422 behavior)
    if file_size == 0:
        return False, StructuredError(
            code=ErrorCode.FILE_EMPTY,
            message="File is empty. Upload a valid audit artifact.",
            details={"size": 0}
        )
    
    # Min size check
    if file_size < settings.min_file_size:
        return False, StructuredError(
            code=ErrorCode.FILE_TOO_SMALL,
            message=f"File too small ({file_size} bytes). Minimum size is {settings.min_file_size} bytes.",
            details={"size": file_size, "min_size": settings.min_file_size}
        )
    
    # Max size check (matches existing 413 behavior)
    if file_size > settings.max_file_size:
        return False, StructuredError(
            code=ErrorCode.FILE_TOO_LARGE,
            message=f"File too large. Maximum size is {settings.max_file_size // 1_000_000}MB.",
            details={"size": file_size, "max_size": settings.max_file_size}
        )
    
    return True, None


async def validate_upload(
    file: UploadFile,
    validate_extension: bool = True,
    validate_mime: bool = True
) -> FileValidationResult:
    """
    Complete file validation with streaming support.
    
    This function combines all validation steps:
    1. Extension validation (if enabled)
    2. MIME type validation (if enabled)
    3. Streaming file read with size checks
    
    All validations are opt-out via feature flags.
    
    Args:
        file: FastAPI UploadFile
        validate_extension: Whether to validate file extension
        validate_mime: Whether to validate MIME type
        
    Returns:
        FileValidationResult with contents or error
    """
    # Extension validation (if enabled)
    if validate_extension:
        ext_valid, ext_error = validate_file_extension(file.filename or "")
        if not ext_valid:
            return FileValidationResult(valid=False, error=ext_error)
    
    # MIME type validation (if enabled)
    if validate_mime:
        mime_valid, mime_error = validate_mime_type(file.content_type)
        if not mime_valid:
            return FileValidationResult(valid=False, error=mime_error)
    
    # Read file with streaming
    result = await read_file_streaming(file)
    if not result.valid:
        return result
    
    # Size validation (always enabled to preserve existing behavior)
    size_valid, size_error = validate_file_size(result.contents)
    if not size_valid:
        return FileValidationResult(valid=False, error=size_error)
    
    return result


def compute_file_hash(contents: bytes) -> str:
    """
    Compute SHA-256 hash of file contents.
    
    This matches the existing hashing logic in the pipeline.
    
    Args:
        contents: File contents
        
    Returns:
        64-character lowercase hex hash
    """
    return hashlib.sha256(contents).hexdigest()


def compute_file_hash_from_path(path: str, chunk_size: int = 1 * 1024 * 1024) -> str:
    """
    Compute SHA-256 hash of file at path using streaming.
    Low memory: never loads full file into RAM.
    
    Args:
        path: Path to file
        chunk_size: Read chunk size (default 1 MiB)
        
    Returns:
        64-character lowercase hex hash
    """
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()
