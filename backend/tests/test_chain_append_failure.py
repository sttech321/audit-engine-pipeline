from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_upload_returns_500_when_chain_append_fails(monkeypatch, sample_valid_content):
    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    # upload router imports add_artifact_block directly; patch the router symbol.
    import app.routers.upload as upload_router

    monkeypatch.setattr(upload_router, "add_artifact_block", boom)

    r = client.post(
        "/api/upload",
        files={"file": ("x.rim95", sample_valid_content, "application/octet-stream")},
    )
    assert r.status_code == 500
    data = r.json()
    # Structured errors may be enabled/disabled; accept either format.
    if isinstance(data, dict) and "error" in data.get("detail", {}):
        assert data["detail"]["error"]["code"] == "CHAIN_APPEND_FAILED"

