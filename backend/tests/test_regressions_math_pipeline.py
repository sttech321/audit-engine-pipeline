import pytest

from app.models.metadata_schemas import ArtifactFormat
from app.services import rim_wrapper
from app.services.metadata_parser import detect_format
from app.utils.penrose import extract_penrose_from_report
from rim_os_v2 import _pentagrid_tau


def test_pentagrid_tau_has_five_independent_offsets():
    tau = _pentagrid_tau("00" * 32)

    assert len(tau) == 5
    assert tau[4] != tau[0]


def test_run_rim_audit_accepts_nested_genesis_frame_hash(monkeypatch):
    def fake_audit_file(file_path, genesis, prev_state, progress_callback):
        return {
            "schema": rim_wrapper.EXPECTED_SCHEMA,
            "genesis": {"frame_hash": rim_wrapper.GENESIS_FRAME_HASH},
        }

    monkeypatch.setattr(rim_wrapper, "audit_file", fake_audit_file)

    report = rim_wrapper.run_rim_audit("dummy.bin")

    assert report["schema"] == rim_wrapper.EXPECTED_SCHEMA


def test_extract_penrose_prefers_first_chunk_tile_hash():
    report = {
        "chunks": [
            {
                "tau_omega_norm": 0.25,
                "barycentric": [0.1, 0.2, 0.7],
                "manifold_hash": "m" * 64,
                "tile_hash": "t" * 64,
            }
        ],
        "ledger": {"next_state_hash": "n" * 64},
        "integrity": {"audit_content_sha256": "i" * 64},
    }

    penrose = extract_penrose_from_report(report, fallback_hash="f" * 64)

    assert penrose["tile_hash"] == "t" * 64


def test_detect_format_rejects_noncanonical_rim95_magic():
    content = b"RIM95" + bytes(32)

    assert detect_format(content, "test.rim95") == ArtifactFormat.UNKNOWN
