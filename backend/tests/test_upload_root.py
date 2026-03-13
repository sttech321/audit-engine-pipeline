"""
Legacy root-level upload tests kept compatible with the current PASS97 API.

These mirror the maintained expectations from backend/tests/ while preserving
the ability to run `python -m pytest` from the repository root.
"""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def make_file(name: str, content: bytes):
    return {"file": (name, content, "application/octet-stream")}


def _clear_abuse_stores():
    from app.services.abuse_protection import clear_stores

    clear_stores()


def test_empty_file_rejected():
    r = client.post("/api/upload", files=make_file("empty.rim95", b""))
    assert r.status_code == 422
    data = r.json()
    if isinstance(data["detail"], dict):
        assert "FILE_EMPTY" in str(data["detail"])
    else:
        assert "empty" in data["detail"].lower()


def test_minimum_valid_file():
    content = bytes(range(256)) * 4
    r = client.post("/api/upload", files=make_file("valid.rim95", content))
    assert r.status_code == 200
    assert r.json()["fileInfo"]["size"] == len(content)


def test_same_file_same_hash():
    content = bytes(range(256)) * 4
    _clear_abuse_stores()
    r1 = client.post("/api/upload", files=make_file("test.rim95", content))
    _clear_abuse_stores()
    r2 = client.post("/api/upload", files=make_file("test.rim95", content))
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["fileHash"] == r2.json()["fileHash"]


def test_same_file_same_kpis():
    content = bytes(range(256)) * 4
    _clear_abuse_stores()
    r1 = client.post("/api/upload", files=make_file("test.rim95", content))
    _clear_abuse_stores()
    r2 = client.post("/api/upload", files=make_file("test.rim95", content))
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["kpis"] == r2.json()["kpis"]


def test_same_file_same_verification():
    content = bytes(range(256)) * 4
    _clear_abuse_stores()
    r1 = client.post("/api/upload", files=make_file("test.rim95", content))
    _clear_abuse_stores()
    r2 = client.post("/api/upload", files=make_file("test.rim95", content))
    assert r1.status_code == 200
    assert r2.status_code == 200
    v1 = r1.json()["verification"]
    v2 = r2.json()["verification"]
    assert v1["status"] == v2["status"]
    assert v1["confidence"] == v2["confidence"]
    assert v1["checks"] == v2["checks"]


def test_different_files_different_hashes():
    r1 = client.post("/api/upload", files=make_file("a.rim95", b"file_alpha"))
    _clear_abuse_stores()
    r2 = client.post("/api/upload", files=make_file("b.rim95", b"file_beta"))
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["fileHash"] != r2.json()["fileHash"]


def test_invalid_content_fails_validation():
    r = client.post("/api/upload", files=make_file("bad.rim95", b"236"))
    if r.status_code == 200:
        assert r.json()["verification"]["status"] in [
            "Verification Failed",
            "Verified with Warnings",
        ]
    else:
        assert r.status_code == 422


def test_response_structure():
    content = bytes(range(256)) * 4
    r = client.post("/api/upload", files=make_file("test.rim95", content))
    assert r.status_code == 200
    data = r.json()
    assert "fileInfo" in data
    assert "kpis" in data
    assert "verification" in data
    assert "fileHash" in data
    assert "uploadId" in data
    assert "metadata" in data
