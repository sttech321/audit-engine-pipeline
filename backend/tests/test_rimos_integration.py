"""
Integration tests for canonical RIM-OS v2 engine.

These tests verify that:
- run_rim_audit() returns a well-formed report
- Artifact-chain block linkage works correctly
- The /api/upload endpoint surfaces the canonical RIM-OS score and hash
"""
import os
import tempfile
import hashlib

from fastapi.testclient import TestClient

from app.main import app
from app.services.artifact_chain import add_artifact_block
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
    assert "events_hash" in ledger
    assert f"prev_{'state'}" not in ledger
    assert f"next_{'state'}_hash" not in ledger


def test_rimos_ledger_chaining(sample_valid_content):
    """Artifact-chain prev_block_hash / block_hash should form a proper hash chain."""
    path = _write_temp(sample_valid_content, "chain.rim95")
    try:
        first = run_rim_audit(path)
        second = run_rim_audit(path)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass

    artifact_hash = hashlib.sha256(sample_valid_content).hexdigest()
    first_block = add_artifact_block(first, artifact_hash)
    second_block = add_artifact_block(second, artifact_hash)

    assert second_block["prev_block_hash"] == first_block["block_hash"]
    assert second_block["block_hash"] != first_block["block_hash"]


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


def test_api_extended_report_exposes_eu_ai_act_attachment(sample_valid_content):
    """Extended report should include the additive EU AI Act attachment fields."""
    resp = client.post("/api/upload", files=make_file("eu.rim95", sample_valid_content))
    assert resp.status_code == 200
    upload_id = resp.json()["uploadId"]

    extended = client.get(f"/api/report/{upload_id}/extended")
    assert extended.status_code == 200
    data = extended.json()

    assert "EU_AI_ACT_FULL" in data
    assert "EU_AI_ACT_HASH" in data
    assert isinstance(data["EU_AI_ACT_FULL"], dict)
    assert isinstance(data["EU_AI_ACT_HASH"], str)
    assert data["EU_AI_ACT_FULL"]["audit_hash"] == data["EU_AI_ACT_HASH"]


def test_same_input_uploaded_twice_produces_different_svg(sample_valid_content):
    first = client.post("/api/upload", files=make_file("same-a.rim95", sample_valid_content))
    second = client.post("/api/upload", files=make_file("same-b.rim95", sample_valid_content))
    assert first.status_code == 200
    assert second.status_code == 200

    first_svg = client.get(f"/api/report/{first.json()['uploadId']}/svg")
    second_svg = client.get(f"/api/report/{second.json()['uploadId']}/svg")

    assert first_svg.status_code == 200
    assert second_svg.status_code == 200
    assert first_svg.text != second_svg.text


def test_upload_order_changes_rendered_svg_pairs(sample_valid_content, monkeypatch, tmp_path):
    from app.config import get_settings

    content_a = sample_valid_content
    content_b = sample_valid_content + b"order-sensitive"

    def run_pair(chain_name: str, first_content: bytes, second_content: bytes):
        monkeypatch.setenv("ARTIFACT_CHAIN_PATH", str(tmp_path / f"{chain_name}.json"))
        get_settings.cache_clear()
        first = client.post("/api/upload", files=make_file(f"{chain_name}-1.rim95", first_content))
        second = client.post("/api/upload", files=make_file(f"{chain_name}-2.rim95", second_content))
        assert first.status_code == 200
        assert second.status_code == 200
        first_svg = client.get(f"/api/report/{first.json()['uploadId']}/svg")
        second_svg = client.get(f"/api/report/{second.json()['uploadId']}/svg")
        assert first_svg.status_code == 200
        assert second_svg.status_code == 200
        return first_svg.text, second_svg.text

    ab = run_pair("ab", content_a, content_b)
    ba = run_pair("ba", content_b, content_a)

    assert ab[0] != ab[1]
    assert ba[0] != ba[1]
    assert set(ab) != set(ba)

