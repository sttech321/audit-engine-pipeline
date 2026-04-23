"""
Local artifact-position blockchain storage.

This layer is additive: it consumes already-computed map coordinates from the
RIM-OS report and appends them to a local JSON chain without changing the
underlying mathematical pipeline.
"""
from __future__ import annotations

import json
import os
import threading
import tempfile
from pathlib import Path
from typing import Any, Dict, List

from app.config import get_settings


_CHAIN_LOCK = threading.Lock()
_GENESIS_TIMESTAMP = "2026-01-01T00:00:00Z"
_PIPELINE_VERSION = "v3.0.0"
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


def canonical_block_hash(block: Dict[str, Any]) -> str:
    """Public helper for recomputing a block hash (excludes existing block_hash)."""
    return _canonical_hash({k: v for k, v in block.items() if k != "block_hash"})


def _chain_seed_path() -> Path:
    """
    RIM-203: persist the self-refining chain seed.

    Stored alongside the chain JSON so tenant-scoped chain paths naturally scope the seed.
    """
    chain_path = _chain_path()
    return chain_path.parent / "chain_seed.txt"


def compute_chain_seed(chain: List[Dict[str, Any]]) -> str:
    """
    RIM-203: deterministic seed over the entire chain state.

    The Reference Model treats the seed as the chain's signature. This function hashes a
    canonical, order-stable subset of each block that must change whenever the chain changes.
    """
    import hashlib

    normalized_blocks: List[Dict[str, Any]] = []
    for block in sorted(chain or [], key=lambda b: b.get("index", 0)):
        tau_values = block.get("tau_vectors", [])
        if not isinstance(tau_values, list):
            tau_values = [tau_values]

        normalized_tau: List[float] = []
        for value in tau_values:
            try:
                normalized_tau.append(float(value))
            except (TypeError, ValueError):
                continue

        anchors = block.get("anchors", [])
        if not isinstance(anchors, list):
            anchors = [str(anchors)]

        normalized_blocks.append(
            {
                "index": int(block.get("index", 0)),
                "block_hash": str(block.get("block_hash", "")),
                "tau_vectors": normalized_tau,
                "anchors": [str(anchor) for anchor in anchors],
            }
        )

    payload = json.dumps(normalized_blocks, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def get_chain_seed() -> str:
    """Return persisted chain seed if present, else compute from chain."""
    path = _chain_seed_path()
    try:
        if path.exists():
            return path.read_text(encoding="utf-8").strip()
    except OSError:
        pass
    chain = get_artifact_chain()
    return compute_chain_seed(chain)


def _persist_chain_seed_unlocked(chain: List[Dict[str, Any]]) -> str:
    seed = compute_chain_seed(chain)
    _atomic_write_text(_chain_seed_path(), seed)
    return seed

def _genesis_block() -> Dict[str, Any]:
    block = {
        "index": 0,
        "type": "GENESIS",
        "timestamp": _GENESIS_TIMESTAMP,
        "anchors": _GENESIS_ANCHORS,
        "pipeline_version": _PIPELINE_VERSION,
    }
    return {**block, "block_hash": _canonical_hash(block)}


def _load_chain_unlocked() -> List[Dict[str, Any]]:
    path = _chain_path()
    if not path.exists():
        chain = [_genesis_block()]
        _atomic_write_text(path, json.dumps(chain, indent=2))
        _persist_chain_seed_unlocked(chain)
        return chain

    try:
        chain = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        chain = []

    if not chain:
        chain = [_genesis_block()]
        _atomic_write_text(path, json.dumps(chain, indent=2))
        _persist_chain_seed_unlocked(chain)
        return chain

    return chain


def _atomic_write_text(path: Path, content: str) -> None:
    """
    RIM-201: atomic write invariant.

    Write to a temp file in the same directory, fsync, then os.replace() into place.
    This prevents chain corruption on crashes/power loss (Windows + POSIX safe).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, path)
    finally:
        try:
            if os.path.exists(tmp_name):
                os.remove(tmp_name)
        except OSError:
            pass


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
    k5 = list(map_position.get("k5") or [])
    world_x = float(map_position.get("world_x") or 0.0)
    world_y = float(map_position.get("world_y") or 0.0)

    if not tau_vectors or not manifold_hash or not tile_hash:
        raise ValueError("Map position is incomplete; cannot create artifact block")

    with _CHAIN_LOCK:
        chain = _load_chain_unlocked()
        prev_block = chain[-1]
        prev_ver = prev_block.get("pipeline_version", _PIPELINE_VERSION)
        if prev_ver != _PIPELINE_VERSION:
            raise ValueError("pipeline_version mismatch; refusing to append")

        # RIM-502: record seed at time of commit (seed over blocks 0..n-1).
        chain_seed_at_commit = compute_chain_seed(chain)
        block = {
            "index": len(chain),
            "timestamp": rim_report.get("time_utc") or _GENESIS_TIMESTAMP,
            "artifact_hash": artifact_hash,
            "pipeline_version": _PIPELINE_VERSION,
            "chain_seed_at_commit": chain_seed_at_commit,
            "tau_vectors": tau_vectors,
            "manifold_hash": manifold_hash,
            "tile_hash": tile_hash,
            "barycentric": barycentric,
            "k5": k5,
            "world_x": world_x,
            "world_y": world_y,
            "prev_block_hash": prev_block.get("block_hash"),
        }
        block["block_hash"] = _canonical_hash(block)
        chain.append(block)
        _atomic_write_text(_chain_path(), json.dumps(chain, indent=2))
        _persist_chain_seed_unlocked(chain)
        return block
