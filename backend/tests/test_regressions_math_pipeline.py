from app.models.metadata_schemas import ArtifactFormat
from app.services import rim_wrapper
from app.services.metadata_parser import detect_format
from app.utils.penrose import extract_penrose_from_report
from rim_os_v2 import compute_k5, k5_to_world_position, _tau_pentagrid_from_k5


def test_compute_k5_and_tau_pentagrid_are_deterministic_spectral():
    chart = {
        "row_means": [3.0, 5.0, 2.0, 8.0, 1.0, 0.0, 0.0, 0.0],
        "gmean": 2.0,
    }
    k5 = compute_k5(chart, scale=50.0)
    assert len(k5) == 5
    tau = _tau_pentagrid_from_k5(k5, scale=50.0)
    assert len(tau) == 5
    assert all(0.0 <= t <= 1.0 for t in tau)
    x, y = k5_to_world_position(k5)
    assert isinstance(x, float) and isinstance(y, float)


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
                "k5": [1.0, -2.0, 0.0, 3.0, -1.0],
                "world_x": 1.5,
                "world_y": -0.5,
                "tau_pentagrid": [0.1, 0.2, 0.3, 0.4, 0.5],
            }
        ],
        "ledger": {"next_state_hash": "n" * 64},
        "integrity": {"audit_content_sha256": "i" * 64},
    }

    penrose = extract_penrose_from_report(report, fallback_hash="f" * 64)

    assert penrose["tile_hash"] == "t" * 64
    assert penrose["k5"][:2] == [1.0, -2.0]
    assert len(penrose["chunk_positions"]) == 1
    assert penrose["chunk_positions"][0]["wx"] == 1.5
    assert penrose["chunk_positions"][0]["wy"] == -0.5
    assert penrose["chunk_positions"][0]["ano"] is False


def test_extract_penrose_prefers_map_position_k5_and_builds_chunk_positions():
    report = {
        "chunks": [
            {
                "chunk_index": 0,
                "tau_omega_norm": 0.25,
                "barycentric": [0.1, 0.2, 0.7],
                "manifold_hash": "m" * 64,
                "tile_hash": "t" * 64,
                "k5": [1.0, 0.0, 0.0, 0.0, 0.0],
                "world_x": 10.0,
                "world_y": -5.0,
                "tau_pentagrid": [0.1, 0.2, 0.3, 0.4, 0.5],
                "separability": 0.9,
                "entropy_bits": 8.0,
            }
        ],
        "map_position": {
            "k5": [9.0, 8.0, 7.0, 6.0, 5.0],
            "world_x": 99.0,
            "world_y": -88.0,
            "tau_vectors": [0.6, 0.6, 0.6, 0.6, 0.6],
        },
        "anomalies": [{"chunk_index": 0}],
        "ledger": {"next_state_hash": "n" * 64},
        "integrity": {"audit_content_sha256": "i" * 64},
    }
    penrose = extract_penrose_from_report(report, fallback_hash="f" * 64)
    assert penrose["k5"] == [9.0, 8.0, 7.0, 6.0, 5.0]
    assert penrose["world_x"] == 99.0
    assert penrose["world_y"] == -88.0
    assert penrose["tau_vectors"][:2] == [0.6, 0.6]
    assert len(penrose["chunk_positions"]) == 1
    cp0 = penrose["chunk_positions"][0]
    assert cp0["wx"] == 10.0 and cp0["wy"] == -5.0
    assert cp0["sep"] == 0.9 and cp0["ent"] == 8.0
    assert cp0["ano"] is True


def test_detect_format_rejects_noncanonical_rim95_magic():
    content = b"RIM95" + bytes(32)

    assert detect_format(content, "test.rim95") == ArtifactFormat.UNKNOWN
