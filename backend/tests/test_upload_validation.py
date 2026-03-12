"""
Tests for file upload validation including extension and MIME type validation.
These tests are ADDITIVE and do not modify existing test behavior.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import make_file

client = TestClient(app)


# ─── Extension Validation Tests ──────────────────────────────────────────────

def test_valid_lm3z_extension(sample_valid_content):
    """Files with .lm3z extension should be accepted."""
    r = client.post("/api/upload", files=make_file("test.lm3z", sample_valid_content))
    assert r.status_code == 200


def test_valid_rim0_extension(sample_valid_content):
    """Files with .rim0 extension should be accepted."""
    r = client.post("/api/upload", files=make_file("test.rim0", sample_valid_content))
    assert r.status_code == 200


def test_valid_rim95_extension(sample_valid_content):
    """Files with .rim95 extension should be accepted."""
    r = client.post("/api/upload", files=make_file("test.rim95", sample_valid_content))
    assert r.status_code == 200


def test_valid_safetensors_extension(sample_valid_content):
    """Files with .safetensors extension should be accepted."""
    r = client.post("/api/upload", files=make_file("test.safetensors", sample_valid_content))
    assert r.status_code == 200


@pytest.mark.parametrize(
    "filename",
    [
        "test.bin",
        "test.gguf",
        "test.pt",
        "test.pth",
        "test.ckpt",
        "test.onnx",
    ],
)
def test_valid_additional_model_extensions(sample_valid_content, filename):
    """Additional binary model extensions should be accepted."""
    r = client.post("/api/upload", files=make_file(filename, sample_valid_content))
    assert r.status_code == 200


def test_invalid_extension_txt(sample_valid_content):
    """Files with .txt extension should be rejected."""
    r = client.post("/api/upload", files=make_file("test.txt", sample_valid_content))
    assert r.status_code == 422
    data = r.json()
    # Check for structured error or legacy error format
    if "error" in data.get("detail", {}):
        assert "FILE_INVALID_EXTENSION" in data["detail"]["error"]["code"]
    else:
        assert "extension" in str(data).lower()


def test_invalid_extension_json(sample_valid_content):
    """Files with .json extension should be rejected."""
    r = client.post("/api/upload", files=make_file("test.json", sample_valid_content))
    assert r.status_code == 422


def test_invalid_extension_pdf(sample_valid_content):
    """Files with .pdf extension should be rejected."""
    r = client.post("/api/upload", files=make_file("report.pdf", sample_valid_content))
    assert r.status_code == 422


def test_no_extension(sample_valid_content):
    """Files without extension should be rejected."""
    r = client.post("/api/upload", files=make_file("noextension", sample_valid_content))
    assert r.status_code == 422


def test_case_insensitive_extension(sample_valid_content):
    """Extension validation should be case-insensitive."""
    from app.services.abuse_protection import clear_stores
    
    r = client.post("/api/upload", files=make_file("test.RIM95", sample_valid_content))
    assert r.status_code == 200
    
    clear_stores()  # Clear stores to allow same content upload
    r = client.post("/api/upload", files=make_file("test.Lm3z", sample_valid_content))
    assert r.status_code == 200

    clear_stores()
    r = client.post("/api/upload", files=make_file("test.SafeTensors", sample_valid_content))
    assert r.status_code == 200

    clear_stores()
    r = client.post("/api/upload", files=make_file("test.GGUF", sample_valid_content))
    assert r.status_code == 200


# ─── MIME Type Validation Tests ──────────────────────────────────────────────

def test_octet_stream_mime_accepted(sample_valid_content):
    """application/octet-stream MIME type should be accepted."""
    r = client.post(
        "/api/upload",
        files={"file": ("test.rim95", sample_valid_content, "application/octet-stream")}
    )
    assert r.status_code == 200


def test_binary_mime_accepted(sample_valid_content):
    """Binary MIME types should be accepted."""
    r = client.post(
        "/api/upload",
        files={"file": ("test.rim95", sample_valid_content, "application/x-binary")}
    )
    assert r.status_code == 200


# ─── Size Validation Tests (Existing Behavior Preserved) ────────────────────

def test_empty_file_rejected():
    """Empty files must be rejected with HTTP 422."""
    r = client.post("/api/upload", files=make_file("empty.rim95", b""))
    assert r.status_code == 422
    data = r.json()
    # Handle both legacy and structured error formats
    if isinstance(data["detail"], dict):
        assert "FILE_EMPTY" in str(data["detail"])
    else:
        assert "empty" in data["detail"].lower()


def test_minimum_size_validation(sample_valid_content):
    """Files meeting minimum size should pass."""
    r = client.post("/api/upload", files=make_file("valid.rim95", sample_valid_content))
    assert r.status_code == 200


def test_file_info_response(sample_valid_content):
    """Response should include correct file info."""
    r = client.post("/api/upload", files=make_file("test.rim95", sample_valid_content))
    assert r.status_code == 200
    
    data = r.json()
    assert data["fileInfo"]["name"] == "test.rim95"
    assert data["fileInfo"]["size"] == len(sample_valid_content)
    assert data["fileInfo"]["type"] == "application/octet-stream"


# ─── Combined Validation Tests ───────────────────────────────────────────────

def test_all_validation_passes(sample_valid_content):
    """Valid file should pass all validation stages."""
    r = client.post("/api/upload", files=make_file("valid.rim95", sample_valid_content))
    assert r.status_code == 200
    
    data = r.json()
    assert "fileHash" in data
    assert "uploadId" in data
    assert "kpis" in data
    assert "verification" in data


def test_validation_does_not_affect_pipeline_output(sample_valid_content):
    """New validation should not change pipeline output for valid files."""
    from app.services.abuse_protection import clear_stores
    
    # Upload same file twice
    r1 = client.post("/api/upload", files=make_file("test.rim95", sample_valid_content))
    clear_stores()  # Clear stores to allow same content upload
    r2 = client.post("/api/upload", files=make_file("test.rim95", sample_valid_content))
    
    assert r1.status_code == 200
    assert r2.status_code == 200
    
    # KPIs and file hash should be identical
    assert r1.json()["fileHash"] == r2.json()["fileHash"]
    assert r1.json()["kpis"] == r2.json()["kpis"]
