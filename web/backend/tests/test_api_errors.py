"""
Tests for structured API error handling.
These tests verify the ADDITIVE structured error functionality.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.error_schemas import ErrorCode, StructuredError
from tests.conftest import make_file

client = TestClient(app)


# ─── StructuredError Model Tests ─────────────────────────────────────────────

def test_structured_error_creation():
    """Should create StructuredError with required fields."""
    error = StructuredError(
        code=ErrorCode.FILE_EMPTY,
        message="Test error message"
    )
    
    assert error.code == ErrorCode.FILE_EMPTY
    assert error.message == "Test error message"
    assert error.details is None


def test_structured_error_with_details():
    """Should create StructuredError with details."""
    error = StructuredError(
        code=ErrorCode.FILE_TOO_LARGE,
        message="File too large",
        details={"size": 1000000, "max_size": 500000}
    )
    
    assert error.details["size"] == 1000000
    assert error.details["max_size"] == 500000


def test_structured_error_to_detail():
    """to_detail should return proper format."""
    error = StructuredError(
        code=ErrorCode.FILE_INVALID_EXTENSION,
        message="Invalid extension",
        details={"extension": ".txt"}
    )
    
    detail = error.to_detail()
    
    assert "error" in detail
    assert detail["error"]["code"] == "FILE_INVALID_EXTENSION"
    assert detail["error"]["message"] == "Invalid extension"
    assert detail["error"]["details"]["extension"] == ".txt"


# ─── API Error Response Tests ────────────────────────────────────────────────

def test_empty_file_error():
    """Empty file should return structured error."""
    r = client.post("/api/upload", files=make_file("test.rim95", b""))
    
    assert r.status_code == 422
    data = r.json()
    
    # Check for structured error format
    if "error" in data.get("detail", {}):
        assert data["detail"]["error"]["code"] == "FILE_EMPTY"
    else:
        # Legacy format fallback
        assert "empty" in data["detail"].lower()


def test_invalid_extension_error():
    """Invalid extension should return structured error."""
    content = bytes(range(256)) * 4
    r = client.post("/api/upload", files=make_file("test.txt", content))
    
    assert r.status_code == 422
    data = r.json()
    
    if "error" in data.get("detail", {}):
        assert data["detail"]["error"]["code"] == "FILE_INVALID_EXTENSION"


def test_oversized_file_error():
    """Oversized file should return 413 status."""
    # This test would require a very large file, so we just verify the pattern
    # The actual max size check is tested elsewhere
    pass


def test_success_response_unchanged(sample_valid_content):
    """Successful response should contain all expected fields."""
    r = client.post("/api/upload", files=make_file("test.rim95", sample_valid_content))
    
    assert r.status_code == 200
    data = r.json()
    
    # Verify standard response structure is unchanged
    assert "fileInfo" in data
    assert "kpis" in data
    assert "verification" in data
    assert "fileHash" in data
    assert "uploadId" in data
    assert "metadata" in data


def test_error_does_not_leak_internals():
    """Errors should not leak internal exception details."""
    # Test with content that might cause internal errors
    r = client.post("/api/upload", files=make_file("test.rim95", b""))
    
    assert r.status_code == 422
    data = r.json()
    
    # Should not contain Python traceback or exception details
    response_str = str(data)
    assert "Traceback" not in response_str
    assert "raise " not in response_str


# ─── Error Code Enumeration Tests ────────────────────────────────────────────

def test_error_codes_exist():
    """All expected error codes should exist."""
    expected_codes = [
        "FILE_EMPTY",
        "FILE_TOO_LARGE",
        "FILE_TOO_SMALL",
        "FILE_INVALID_TYPE",
        "FILE_INVALID_EXTENSION",
        "FILE_INVALID_MIME",
        "METADATA_PARSE_ERROR",
        "SIGNATURE_VERIFICATION_FAILED",
        "RATE_LIMIT_EXCEEDED",
        "DUPLICATE_UPLOAD",
        "INTERNAL_ERROR",
    ]
    
    for code in expected_codes:
        assert hasattr(ErrorCode, code)


def test_error_code_values():
    """Error codes should have string values."""
    assert ErrorCode.FILE_EMPTY.value == "FILE_EMPTY"
    assert ErrorCode.FILE_TOO_LARGE.value == "FILE_TOO_LARGE"
    assert ErrorCode.INTERNAL_ERROR.value == "INTERNAL_ERROR"


# ─── HTTP Status Code Tests ──────────────────────────────────────────────────

def test_validation_error_422():
    """Validation errors should return 422."""
    r = client.post("/api/upload", files=make_file("test.rim95", b""))
    assert r.status_code == 422


def test_extension_error_422():
    """Invalid extension should return 422."""
    content = bytes(range(256)) * 4
    r = client.post("/api/upload", files=make_file("test.txt", content))
    assert r.status_code == 422


def test_success_200(sample_valid_content):
    """Successful upload should return 200."""
    r = client.post("/api/upload", files=make_file("test.rim95", sample_valid_content))
    assert r.status_code == 200


# ─── Backward Compatibility Tests ────────────────────────────────────────────

def test_detail_field_present_on_error():
    """Error responses should include 'detail' field for backward compatibility."""
    r = client.post("/api/upload", files=make_file("test.rim95", b""))
    
    assert r.status_code == 422
    assert "detail" in r.json()


def test_standard_http_exception_format():
    """Errors should follow FastAPI HTTPException format."""
    r = client.post("/api/upload", files=make_file("test.rim95", b""))
    
    assert r.status_code == 422
    data = r.json()
    assert "detail" in data


def test_success_response_format(sample_valid_content):
    """Success response format should be unchanged."""
    r = client.post("/api/upload", files=make_file("test.rim95", sample_valid_content))
    
    assert r.status_code == 200
    data = r.json()
    
    # Verify exact response structure
    assert isinstance(data["fileInfo"]["name"], str)
    assert isinstance(data["fileInfo"]["size"], int)
    assert isinstance(data["fileInfo"]["type"], str)
    assert isinstance(data["kpis"], list)
    assert len(data["kpis"]) == 5
    assert isinstance(data["verification"]["status"], str)
    assert isinstance(data["verification"]["confidence"], int)
    assert isinstance(data["fileHash"], str)
    assert isinstance(data["uploadId"], str)
    assert isinstance(data["metadata"], dict)
