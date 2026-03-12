"""
Local artifact-position blockchain storage.

This layer is additive: it consumes already-computed map coordinates from the
RIM-OS report and appends them to a local JSON chain without changing the
underlying mathematical pipeline.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Dict, List

from app.config import get_settings


_CHAIN_LOCK = threading.Lock()
_GENESIS_TIMESTAMP = "2026-01-01T00:00:00Z"
_GENESIS_ANCHORS = [
    "fine_structure_constant",
    "einstein_field_equations",
    "boltzmann_entropy",
]


def _chain_path() -> Path:
    settings = get_settings()
    configured = settings.artifact_chain_path
    path = Path(configured)
    if not path.is_absolute():
        path = Path(__file__).resolve().parents[2] / configured
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _canonical_hash(obj: Dict[str, Any]) -> str:
    import hashlib

    payload = json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _genesis_block() -> Dict[str, Any]:
    block = {
        "index": 0,
        "type": "GENESIS",
        "timestamp": _GENESIS_TIMESTAMP,
        "anchors": _GENESIS_ANCHORS,
    }
    return {**block, "block_hash": _canonical_hash(block)}


def _load_chain_unlocked() -> List[Dict[str, Any]]:
    path = _chain_path()
    if not path.exists():
        chain = [_genesis_block()]
        path.write_text(json.dumps(chain, indent=2), encoding="utf-8")
        return chain

    try:
        chain = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        chain = []

    if not chain:
        chain = [_genesis_block()]
        path.write_text(json.dumps(chain, indent=2), encoding="utf-8")
        return chain

    return chain


def get_artifact_chain() -> List[Dict[str, Any]]:
    with _CHAIN_LOCK:
        return _load_chain_unlocked()


def add_artifact_block(rim_report: Dict[str, Any], artifact_hash: str) -> Dict[str, Any]:
    """
    Append a new artifact-position block using existing report coordinates.

    The block represents the artifact's resolved position on the Penrose map.
    """
    map_position = rim_report.get("map_position") or {}
    tau_vectors = list(map_position.get("tau_vectors") or [])
    barycentric = list(map_position.get("barycentric") or [])
    manifold_hash = map_position.get("manifold_hash") or ""
    tile_hash = map_position.get("tile_hash") or ""

    if not tau_vectors or not manifold_hash or not tile_hash:
        raise ValueError("Map position is incomplete; cannot create artifact block")

    with _CHAIN_LOCK:
        chain = _load_chain_unlocked()
        prev_block = chain[-1]
        block = {
            "index": len(chain),
            "timestamp": rim_report.get("time_utc") or _GENESIS_TIMESTAMP,
            "artifact_hash": artifact_hash,
            "tau_vectors": tau_vectors,
            "manifold_hash": manifold_hash,
            "tile_hash": tile_hash,
            "barycentric": barycentric,
            "prev_block_hash": prev_block.get("block_hash"),
        }
        block["block_hash"] = _canonical_hash(block)
        chain.append(block)
        _chain_path().write_text(json.dumps(chain, indent=2), encoding="utf-8")
        return block
