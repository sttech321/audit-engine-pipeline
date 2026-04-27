import os
import tempfile

from app.models.metadata_schemas import ArtifactFormat
from app.services import rim_wrapper
from app.services.metadata_parser import detect_format
from app.utils.penrose import extract_penrose_from_report
from rim_os_v2 import audit_file, build_genesis, compute_k5_and_tau, kag_invariants, k5_to_world_position


def test_compute_k5_and_tau_pentagrid_are_deterministic_spectral():
    # Build a deterministic synthetic spectrum (shape matters, not scale).
    spec256 = [(i * 17) % 1000 for i in range(256)]
    inv = kag_invariants(spec256)
    k5, tau = compute_k5_and_tau(inv, scale=50.0)
    assert len(k5) == 5
    assert len(tau) == 5
    assert all(0.0 <= t < 1.0 for t in tau)
    x, y = k5_to_world_position(k5)
    assert isinstance(x, float) and isinstance(y, float)


def test_build_genesis_is_deterministic_and_non_degenerate():
    first = build_genesis()
    second = build_genesis()

    assert first == second
    for mint in first["genesis_mints"]:
        tau = mint["tau_pentagrid"]
        assert len(tau) == 5
        assert len({round(v, 12) for v in tau}) > 1
        assert any(0.0 < v < 1.0 for v in tau)
        assert len(mint["k5"]) == 5


def test_audit_barycentric_profiles_vary_against_unified_genesis():
    genesis = build_genesis()

    def _audit_bytes(content: bytes):
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".bin")
        try:
            tmp.write(content)
            tmp.close()
            return audit_file(tmp.name, genesis=genesis, max_chunks=1)
        finally:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass

    first = _audit_bytes(bytes(range(256)) * 4)
    second = _audit_bytes(bytes(reversed(range(256))) * 4)

    first_bary = first["map_position"]["barycentric"]
    second_bary = second["map_position"]["barycentric"]
    assert len(first_bary) == 3
    assert len(second_bary) == 3
    assert first_bary != second_bary


def test_run_rim_audit_accepts_nested_genesis_frame_hash(monkeypatch):
    def fake_audit_file(file_path, genesis, progress_callback):
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
                "k5": [1.0, -2.0, 0.0, 3.0, -1.0],
                "world_x": 1.5,
                "world_y": -0.5,
                "tau_pentagrid": [0.1, 0.2, 0.3, 0.4, 0.5],
            }
        ],
        "ledger": {"events_hash": "e" * 64},
        "integrity": {"audit_content_sha256": "i" * 64},
    }

    penrose = extract_penrose_from_report(report, fallback_hash="f" * 64)

    assert penrose["tile_hash"] == "t" * 64
    assert penrose["k5"][:2] == [1.0, -2.0]


def test_detect_format_rejects_noncanonical_rim95_magic():
    content = b"RIM95" + bytes(32)

    assert detect_format(content, "test.rim95") == ArtifactFormat.UNKNOWN
