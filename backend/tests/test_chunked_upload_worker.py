import asyncio
import os

import pytest

import app.routers.report as report_router
import app.services.chunked_upload_service as chunked_module
from app.services.chunked_upload_service import ChunkedUploadService


@pytest.mark.asyncio
async def test_chunked_session_restores_from_disk_after_restart():
    service = ChunkedUploadService()
    content = bytes(range(64))
    upload_id, _ = await service.create_session(
        filename="resume.rim95",
        total_size=len(content),
        total_chunks=1,
        chunk_size=len(content),
    )

    ok, error = await service.write_chunk(upload_id, 0, content)
    assert ok is True
    assert error is None

    restored = ChunkedUploadService()
    status = await restored.get_status(upload_id)

    assert status is not None
    assert status["uploaded_chunks"] == [0]
    assert status["status"] == "uploading"

    session = await restored._get_session(upload_id)
    assert session is not None
    restored._delete_session_files(session)


@pytest.mark.asyncio
async def test_chunked_complete_uses_process_worker(monkeypatch):
    service = ChunkedUploadService()
    content = bytes(range(64))
    upload_id, _ = await service.create_session(
        filename="worker.rim95",
        total_size=len(content),
        total_chunks=1,
        chunk_size=len(content),
    )

    ok, error = await service.write_chunk(upload_id, 0, content)
    assert ok is True
    assert error is None

    calls = {"worker": 0}

    async def fake_execute_in_worker(func, *args, **kwargs):
        calls["worker"] += 1
        progress_callback = args[2]
        assert progress_callback is not None
        progress_callback(42.0)
        await asyncio.sleep(0.05)
        return {
            "summary": {
                "risk_level": "LOW",
                "integrity_score_0_100": 98.0,
                "anomaly_fraction": 0.0,
                "avg_kag_separability": 0.75,
                "anomaly_count": 0,
                "avg_entropy_bits": 7.9,
                "avg_penrose_match": 0.82,
            },
            "time_utc": "2026-03-12T00:00:00Z",
            "ledger": {
                "prev_state": None,
                "next_state_hash": "n" * 64,
                "events_hash": "e" * 64,
            },
            "integrity": {"audit_content_sha256": "i" * 64},
            "chunks": [
                {
                    "tau_omega_norm": 0.2,
                    "barycentric": [0.1, 0.2, 0.7],
                    "manifold_hash": "m" * 64,
                    "tile_hash": "t" * 64,
                }
            ],
        }

    monkeypatch.setattr(chunked_module, "execute_in_worker", fake_execute_in_worker)
    monkeypatch.setattr(chunked_module, "compute_file_hash_from_path", lambda path: "h" * 64)
    monkeypatch.setattr(report_router, "cache_audit_result", lambda upload_id, extended: None)

    result = await service.complete_and_process(upload_id)

    assert calls["worker"] == 1
    assert result["file_hash"] == "h" * 64
    assert not os.path.exists(service._sessions[upload_id].temp_path)
