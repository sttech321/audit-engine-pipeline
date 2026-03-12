"""
Integration tests for canonical RIM-OS v2 engine.

These tests verify that:
- run_rim_audit() returns a well-formed report
- Ledger chaining via prev_state / next_state_hash works correctly
- The /api/upload endpoint surfaces the canonical RIM-OS score and hash
"""
import os
import tempfile

from fastapi.testclient import TestClient

from app.main import app
from app.services.rim_wrapper import run_rim_audit
from rim_os_v2 import build_genesis
from tests.conftest import make_file


client = TestClient(app)


def _write_temp(contents: bytes, name: str = "test.bin") -> str:
    suffix = os.path.splitext(name)[1] or ".bin"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(contents)
    tmp_path = tmp.name
    tmp.close()
    return tmp_path


def test_run_rim_audit_basic_structure(sample_valid_content):
    """run_rim_audit should return a RIM-OS report with expected top-level fields."""
    path = _write_temp(sample_valid_content, "sample.rim95")
    try:
        report = run_rim_audit(path)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass

    genesis = build_genesis()

    # Schema/frame invariants
    assert report["schema"] == genesis["schema"]
    assert report["genesis_frame_hash"] == genesis["frame_hash"]

    # Required sections
    assert "summary" in report
    assert "ledger" in report
    assert "integrity" in report

    summary = report["summary"]
    integrity = report["integrity"]
    ledger = report["ledger"]

    assert "integrity_score_0_100" in summary
    assert "risk_level" in summary
    assert "audit_content_sha256" in integrity
    assert "next_state_hash" in ledger


def test_rimos_ledger_chaining(sample_valid_content):
    """prev_state / next_state_hash should form a proper hash chain."""
    path = _write_temp(sample_valid_content, "chain.rim95")
    try:
        first = run_rim_audit(path)
        prev_state = first["ledger"]["next_state_hash"]

        second = run_rim_audit(path, prev_state=prev_state)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass

    first_ledger = first["ledger"]
    second_ledger = second["ledger"]

    # Chaining: second.prev_state is first.next_state_hash
    assert second_ledger["prev_state"] == first_ledger["next_state_hash"]
    # And next_state_hash should evolve when prev_state changes
    assert second_ledger["next_state_hash"] != first_ledger["next_state_hash"]


def test_api_upload_uses_rimos_score(sample_valid_content):
    """
    /api/upload should surface the canonical RIM-OS integrity score
    in the first KPI ("Audit Score").
    """
    path = _write_temp(sample_valid_content, "api.rim95")
    try:
        direct_report = run_rim_audit(path)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass

    expected_score = direct_report["summary"]["integrity_score_0_100"]

    resp = client.post("/api/upload", files=make_file("api.rim95", sample_valid_content))
    assert resp.status_code == 200
    data = resp.json()

    # API still returns a list of KPIs; first one is "Audit Score"
    kpis = data["kpis"]
    assert len(kpis) >= 1
    assert kpis[0]["label"] == "Audit Score"
    assert kpis[0]["value"] == expected_score


def test_api_extended_report_exposes_map_position(sample_valid_content):
    """Extended report should expose Penrose map coordinates for the artifact."""
    resp = client.post("/api/upload", files=make_file("map.rim95", sample_valid_content))
    assert resp.status_code == 200
    payload = resp.json()
    upload_id = payload["uploadId"]

    assert "artifactBlock" in payload
    artifact_block = payload["artifactBlock"]
    assert artifact_block["index"] == 1
    assert len(artifact_block["tau_vectors"]) == 5
    assert isinstance(artifact_block["block_hash"], str)

    extended = client.get(f"/api/report/{upload_id}/extended")
    assert extended.status_code == 200
    data = extended.json()

    assert "map_position" in data
    assert "artifact_block" in data
    map_position = data["map_position"]
    artifact_block = data["artifact_block"]
    assert len(map_position["tau_vectors"]) == 5
    assert len(map_position["barycentric"]) == 3
    assert isinstance(map_position["manifold_hash"], str)
    assert isinstance(map_position["tile_hash"], str)
    assert artifact_block["manifold_hash"] == map_position["manifold_hash"]
    assert artifact_block["tile_hash"] == map_position["tile_hash"]

