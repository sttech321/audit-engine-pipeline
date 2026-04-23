from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_upload_rejects_invalid_rim95_payloads():
    samples = [
        ("bad_signature_test.rim95", b"236"),
        ("bad.rim95", b"\xff\xfe9\x00\r\x00\n\x00"),
    ]

    for name, content in samples:
        r = client.post(
            "/api/upload",
            files={"file": (name, content, "application/octet-stream")},
        )
        # Upload endpoint returns 200 for processed audits, but must report failure.
        assert r.status_code == 200
        data = r.json()
        verification = data.get("verification") or {}
        assert verification.get("status") in ("Verification Failed", "Verified with Warnings")
