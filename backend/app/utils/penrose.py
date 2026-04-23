"""
Extract Penrose visualization parameters from RIM-OS audit report.

Each audit produces a unique, deterministic Penrose fingerprint derived from
the first chunk's manifold geometry and the ledger state.
"""
from typing import Any, Dict, List

from rim_os_v2 import _tau_pentagrid_from_k5


def extract_penrose_from_report(report: Dict[str, Any], fallback_hash: str = "") -> Dict[str, Any]:
    """
    Extract Penrose mint parameters from RIM-OS audit report.

    Returns k5 world coordinates (not hash-normalized τ) for correct
    positioning on the global Penrose field.
    """
    chunks = report.get("chunks", [])
    first_chunk = chunks[0] if chunks else {}

    k5 = first_chunk.get("k5")
    if not isinstance(k5, list) or len(k5) < 5:
        k5 = [0.0] * 5
    else:
        k5 = [float(k5[i]) for i in range(5)]

    wx = float(first_chunk.get("world_x", 0.0))
    wy = float(first_chunk.get("world_y", 0.0))

    tau_pent = first_chunk.get("tau_pentagrid")
    if isinstance(tau_pent, list) and len(tau_pent) >= 5:
        tau_vectors: List[float] = [float(tau_pent[i]) for i in range(5)]
    else:
        tau_vectors = _tau_pentagrid_from_k5(k5, scale=50.0)

    barycentric = first_chunk.get("barycentric", [0.0, 0.0, 0.0])
    if not isinstance(barycentric, list):
        barycentric = [0.0, 0.0, 0.0]

    ledger = report.get("ledger", {}) or {}
    integrity = report.get("integrity", {}) or {}
    # RIM-205: pipeline-level next_state_hash is being phased out; prefer artifact_chain linkage.
    artifact_block = report.get("artifact_block", {}) or {}
    next_state = artifact_block.get("block_hash") or ledger.get("next_state_hash") or fallback_hash
    manifold_hash = (first_chunk.get("manifold_hash")
                     or integrity.get("audit_content_sha256", ""))

    tau_omega = float(first_chunk.get("tau_omega_norm", 0.5))
    theta = float(barycentric[0]) if barycentric else 0.0

    return {
        "k5": k5,
        "world_x": wx,
        "world_y": wy,
        "barycentric": barycentric,
        "penrose_hash": manifold_hash,
        "tile_hash": (first_chunk.get("tile_hash")
                      or (next_state[:16] if next_state else "")),
        "tau_vectors": tau_vectors,
        # Legacy / chart-style API
        "r": tau_omega,
        "theta": theta,
        "tau": tau_omega,
        "sector": int(tau_omega * 5) % 5,
    }
