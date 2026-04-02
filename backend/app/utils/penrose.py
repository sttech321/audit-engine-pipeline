"""
Extract Penrose visualization parameters from RIM-OS audit report.

Each audit produces a unique, deterministic Penrose fingerprint derived from
manifold geometry (preferring aggregated ``map_position``) and the ledger state.
"""
from typing import Any, Dict, List

from rim_os_v2 import _tau_pentagrid_from_k5


def extract_penrose_from_report(report: Dict[str, Any], fallback_hash: str = "") -> Dict[str, Any]:
    """
    Extract Penrose mint parameters from RIM-OS audit report.

    Uses ``report[\"map_position\"]`` for k5 / τ / world anchor when present
    (aggregated across chunks); otherwise falls back to the first chunk.

    Adds ``chunk_positions``: lightweight summaries for pipeline-driven SVG coloring.
    """
    chunks = report.get("chunks", [])
    first_chunk = chunks[0] if chunks else {}
    mp = report.get("map_position") or {}

    # Prefer aggregated map_position k5 (proper multi-chunk average).
    k5 = mp.get("k5")
    if not isinstance(k5, list) or len(k5) < 5:
        k5 = first_chunk.get("k5")
        if not isinstance(k5, list) or len(k5) < 5:
            k5 = [0.0] * 5
        else:
            k5 = [float(k5[i]) for i in range(5)]
    else:
        k5 = [float(k5[i]) for i in range(5)]

    if isinstance(mp, dict) and "world_x" in mp:
        wx = float(mp["world_x"])
    else:
        wx = float(first_chunk.get("world_x", 0.0))
    if isinstance(mp, dict) and "world_y" in mp:
        wy = float(mp["world_y"])
    else:
        wy = float(first_chunk.get("world_y", 0.0))

    tau_from_map = mp.get("tau_vectors")
    if isinstance(tau_from_map, list) and len(tau_from_map) >= 5:
        tau_vectors: List[float] = [float(tau_from_map[i]) for i in range(5)]
    else:
        tau_pent = first_chunk.get("tau_pentagrid")
        if isinstance(tau_pent, list) and len(tau_pent) >= 5:
            tau_vectors = [float(tau_pent[i]) for i in range(5)]
        else:
            tau_vectors = _tau_pentagrid_from_k5(k5, scale=50.0)

    barycentric = first_chunk.get("barycentric", [0.0, 0.0, 0.0])
    if not isinstance(barycentric, list):
        barycentric = [0.0, 0.0, 0.0]

    ledger = report.get("ledger", {}) or {}
    integrity = report.get("integrity", {}) or {}
    next_state = ledger.get("next_state_hash") or fallback_hash
    manifold_hash = (first_chunk.get("manifold_hash")
                     or integrity.get("audit_content_sha256", ""))

    tau_omega = float(first_chunk.get("tau_omega_norm", 0.5))
    theta = float(barycentric[0]) if barycentric else 0.0

    anomaly_indices = {int(a["chunk_index"]) for a in report.get("anomalies", [])
                       if isinstance(a, dict) and "chunk_index" in a}
    chunk_positions: List[Dict[str, Any]] = []
    for c in chunks:
        if not isinstance(c, dict):
            continue
        ck5 = c.get("k5")
        if not isinstance(ck5, list) or len(ck5) < 5:
            continue
        idx = c.get("chunk_index", -1)
        try:
            ci = int(idx) if idx is not None else -1
        except (TypeError, ValueError):
            ci = -1
        chunk_positions.append({
            "wx": float(c.get("world_x", 0.0)),
            "wy": float(c.get("world_y", 0.0)),
            "sep": float(c.get("separability", 0.0)),
            "ent": float(c.get("entropy_bits", 0.0)),
            "ano": ci in anomaly_indices,
        })

    return {
        "k5": k5,
        "world_x": wx,
        "world_y": wy,
        "barycentric": barycentric,
        "penrose_hash": manifold_hash,
        "tile_hash": (first_chunk.get("tile_hash")
                      or (next_state[:16] if next_state else "")),
        "tau_vectors": tau_vectors,
        "chunk_positions": chunk_positions,
        # Legacy / chart-style API
        "r": tau_omega,
        "theta": theta,
        "tau": tau_omega,
        "sector": int(tau_omega * 5) % 5,
    }
