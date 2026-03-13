from fastapi.testclient import TestClient

from app.main import app
from app.routers import report as report_router
from tests.conftest import make_file


client = TestClient(app)


def test_report_survives_in_memory_cache_clear(sample_valid_content):
    upload_response = client.post(
        "/api/upload",
        files=make_file("persistent.rim95", sample_valid_content),
    )
    assert upload_response.status_code == 200

    upload_id = upload_response.json()["uploadId"]

    # Simulate a process-local cache miss, such as after a restart.
    report_router._audit_cache.clear()

    report_response = client.get(f"/api/report/{upload_id}/extended")
    assert report_response.status_code == 200

    data = report_response.json()
    assert data["file_hash"] == upload_response.json()["fileHash"]
    assert "EU_AI_ACT_FULL" in data
    assert "EU_AI_ACT_HASH" in data
