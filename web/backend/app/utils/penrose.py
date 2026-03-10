"""
Extract Penrose visualization parameters from RIM-OS audit report.

Each audit produces a unique, deterministic Penrose fingerprint derived from
the first chunk's manifold geometry and the ledger state.
"""
from typing import Any, Dict


def extract_penrose_from_report(report: Dict[str, Any], fallback_hash: str = "") -> Dict[str, Any]:
    """
    Extract Penrose parameters from RIM audit report chunk data.

    Uses the first chunk as the source of manifold geometry. Falls back to
    ledger/integrity hashes when no chunks are present (e.g. empty file).

    Args:
        report: Full RIM-OS audit report dict (from audit_file)
        fallback_hash: Hash to use when ledger.next_state_hash is missing

    Returns:
        Dict with r, theta, sector, penrose_hash, tau, tile_hash
    """
    chunks = report.get("chunks", [])
    first_chunk = chunks[0] if chunks else {}

    tau_omega = float(first_chunk.get("tau_omega_norm", 0.5))
    barycentric = first_chunk.get("barycentric", [0.0, 0.0, 0.0])
    theta = float(barycentric[0]) if barycentric else 0.0

    ledger = report.get("ledger", {}) or {}
    integrity = report.get("integrity", {}) or {}
    next_state = ledger.get("next_state_hash") or fallback_hash
    manifold_hash = first_chunk.get("manifold_hash") or integrity.get("audit_content_sha256", "")

    return {
        "r": tau_omega,
        "theta": theta,
        "sector": int(tau_omega * 5) % 5,
        "penrose_hash": manifold_hash,
        "tau": tau_omega,
        "tile_hash": next_state[:16] if next_state else "",
    }
