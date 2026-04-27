import hashlib
from typing import List, Tuple

from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import make_file


client = TestClient(app)


def _make_batch_files(file_specs: List[Tuple[str, bytes]]) -> List[Tuple[str, Tuple[str, bytes, str]]]:
    """
    Helper to build the 'files' argument for multipart batch requests.

    file_specs: list of (filename, content)
    """
    return [
        ("files", (name, content, "application/octet-stream"))
        for name, content in file_specs
    ]


def test_batch_upload_success(sample_valid_content):
    """Batch endpoint should successfully process multiple valid files."""
    # Use different contents to avoid triggering replay / deduplication guards.
    content_a = sample_valid_content
    content_b = sample_valid_content + b"varied"
    files = _make_batch_files(
        [
            ("model_a.rim95", content_a),
            ("model_b.rim95", content_b),
        ]
    )

    r = client.post("/api/upload/batch", files=files)
    assert r.status_code == 200

    data = r.json()
    assert "batchId" in data
    assert isinstance(data["batchId"], str)
    assert len(data["results"]) == 2

    for item in data["results"]:
        assert item["status"] == "ok"
        assert "uploadId" in item
        assert "verification" in item
        assert "kpis" in item


def test_batch_partial_failure(sample_valid_content):
    """One bad file should not prevent the rest of the batch from succeeding."""
    files = _make_batch_files(
        [
            ("good.rim95", sample_valid_content),
            ("bad.txt", b"not a valid extension"),
        ]
    )

    r = client.post("/api/upload/batch", files=files)
    assert r.status_code == 200

    data = r.json()
    assert len(data["results"]) == 2

    statuses = {item["fileName"]: item["status"] for item in data["results"]}
    assert statuses["good.rim95"] == "ok"
    assert statuses["bad.txt"] == "failed"


def test_batch_report_generation(sample_valid_content, monkeypatch):
    """Reports (PDF/SVG) should be available for successful batch entries."""
    # Speed: stub the expensive audit engine. Batch tests are verifying API wiring and
    # report availability, not the full Gödel→p-adic→NTT→KAG runtime.
    from app.services import rim_wrapper
    from app.services import pdf_generator as pdf_generator_mod

    def fake_run_rim_audit(file_path: str, chain_seed=None, progress_callback=None):
        return {
            "schema": rim_wrapper.EXPECTED_SCHEMA,
            "time_utc": "2026-01-01T00:00:00Z",
            "input": {"path": "x", "size_bytes": 1, "chunk_count": 1, "chunk_size": 1},
            "summary": {
                "integrity_score_0_100": 95,
                "risk_level": "LOW",
                "avg_entropy_bits": 8.0,
                "avg_penrose_match": 1.0,
                "avg_kag_separability": 0.9,
                "anomaly_count": 0,
                "anomaly_fraction": 0.0,
                "bias_penalty_0_1": 0.0,
                "requires_human_review": False,
                "conformity_passed": True,
            },
            "anomalies": [],
            "chunks": [
                {
                    "chunk_index": 0,
                    "world_x": 0.0,
                    "world_y": 0.0,
                    "separability": 0.9,
                    "entropy_bits": 8.0,
                    "ano": False,
                }
            ],
            "ledger": {"events_hash": "e" * 64},
            "integrity": {"audit_content_sha256": "i" * 64},
            "map_position": {
                "k5": [0.0, 0.0, 0.0, 0.0, 0.0],
                "tau_vectors": [0.5, 0.5, 0.5, 0.5, 0.5],
                "world_x": 0.0,
                "world_y": 0.0,
                "barycentric": [0.33, 0.33, 0.34],
                "manifold_hash": "m" * 64,
                "tile_hash": "t" * 64,
            },
            "genesis_frame_hash": rim_wrapper.GENESIS_FRAME_HASH,
            "EU_AI_ACT": {},
        }

    monkeypatch.setattr(rim_wrapper, "run_rim_audit", fake_run_rim_audit)

    # Speed: stub PDF generation (ReportLab/FPDF work can dominate runtime on Windows CI).
    class _FakePdfGen:
        def generate_report(self, **kwargs):
            return b"%PDF-1.4\n%RIMOS-TEST\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"

    monkeypatch.setattr(pdf_generator_mod, "get_pdf_generator", lambda: _FakePdfGen())

    files = _make_batch_files(
        [
            ("model_batch.rim95", sample_valid_content),
        ]
    )

    r = client.post("/api/upload/batch", files=files)
    assert r.status_code == 200
    result = r.json()["results"][0]
    assert result["status"] == "ok"

    upload_id = result["uploadId"]

    pdf = client.get(f"/api/report/{upload_id}/pdf")
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"

    svg = client.get(f"/api/report/{upload_id}/svg")
    assert svg.status_code == 200
    assert "image/svg+xml" in svg.headers["content-type"]


def test_batch_hash_determinism(sample_valid_content):
    """Batch endpoint should preserve SHA-256 fileHash determinism."""
    from app.services.abuse_protection import clear_stores

    files = _make_batch_files(
        [
            ("deterministic.rim95", sample_valid_content),
        ]
    )

    r1 = client.post("/api/upload/batch", files=files)
    clear_stores()  # avoid replay detection between identical batches
    r2 = client.post("/api/upload/batch", files=files)

    assert r1.status_code == 200
    assert r2.status_code == 200

    res1 = r1.json()["results"][0]
    res2 = r2.json()["results"][0]

    assert res1["status"] == "ok"
    assert res2["status"] == "ok"

    # The backend's fileHash is defined as SHA-256(contents).
    expected = hashlib.sha256(sample_valid_content).hexdigest()
    assert res1["fileHash"] == expected
    assert res2["fileHash"] == expected

