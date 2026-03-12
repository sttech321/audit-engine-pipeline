import json

from app.services.artifact_chain import add_artifact_block, get_artifact_chain


def _sample_report():
    return {
        "time_utc": "2026-03-12T21:00:00Z",
        "map_position": {
            "tau_vectors": [0.34, 0.88, 0.12, 0.77, 0.44],
            "barycentric": [0.2, 0.3, 0.5],
            "manifold_hash": "a" * 64,
            "tile_hash": "b" * 64,
        },
    }


def test_artifact_chain_bootstraps_with_genesis():
    chain = get_artifact_chain()

    assert len(chain) == 1
    assert chain[0]["index"] == 0
    assert chain[0]["type"] == "GENESIS"
    assert chain[0]["anchors"] == [
        "fine_structure_constant",
        "einstein_field_equations",
        "boltzmann_entropy",
    ]
    assert isinstance(chain[0]["block_hash"], str)


def test_add_artifact_block_appends_position_block():
    block = add_artifact_block(_sample_report(), "c" * 64)
    chain = get_artifact_chain()

    assert block["index"] == 1
    assert block["artifact_hash"] == "c" * 64
    assert block["tau_vectors"] == [0.34, 0.88, 0.12, 0.77, 0.44]
    assert block["manifold_hash"] == "a" * 64
    assert block["tile_hash"] == "b" * 64
    assert block["barycentric"] == [0.2, 0.3, 0.5]
    assert block["prev_block_hash"] == chain[0]["block_hash"]
    assert chain[-1]["block_hash"] == block["block_hash"]


def test_artifact_chain_file_contains_serialized_blocks():
    add_artifact_block(_sample_report(), "c" * 64)
    chain = get_artifact_chain()

    serialized = json.dumps(chain)
    assert "GENESIS" in serialized
    assert '"index": 1' in json.dumps(chain, indent=2)
