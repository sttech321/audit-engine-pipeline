from __future__ import annotations

from typing import Any, Callable, Dict, Optional
import time

try:
    # RIM-OS v2 deterministic audit engine (canonical math layer).
    from rim_os_v2 import audit_file, build_genesis
except ImportError as exc:  # pragma: no cover - import wiring error
    raise ImportError(
        "rim_wrapper requires the RIM-OS v2 engine to be importable as "
        "`rim_os_v2`. Ensure `rim_os_v2.py` is on PYTHONPATH."
    ) from exc

from app.logging_config import logger


# ─── Genesis & schema configuration ─────────────────────────────────────────────

GENESIS: Dict[str, Any] = build_genesis()

# RIM-OS schema version this backend is wired against.
EXPECTED_SCHEMA: str = GENESIS.get("schema", "RIM-OS-2.0.0")

# Cached frame hash from Genesis; every audit must report the same value.
GENESIS_FRAME_HASH: str = GENESIS.get("frame_hash", "")


def run_rim_audit(
    file_path: str,
    prev_state: Optional[str] = None,
    chain_seed: Optional[str] = None,
    progress_callback: Optional[Callable[[float], None]] = None,
) -> Dict[str, Any]:
    """
    Run a RIM-OS v2 audit on a single file.

    This is a thin, production-safe wrapper around the canonical `audit_file`
    implementation provided by the RIM-OS client engine.

    Ledger dependency:
        - Each audit produces a `ledger.next_state_hash` value.
        - Backends must persist this hash and pass it back as `prev_state`
          on the next audit to obtain an append-only, chain-linkable ledger.

    Genesis immutability:
        - Genesis is constructed once at module import via `build_genesis()`.
        - The resulting `GENESIS` object and its `frame_hash` define the
          coordinate frame on manifold M and MUST be treated as immutable.
        - All audits must be calculated against the same Genesis instance;
          changing Genesis would break ledger continuity and comparability.

    Math invariants:
        - This wrapper MUST NOT reimplement or alter any of the underlying
          mathematical pipeline (Gödel, p-adic, NTT, KAG, Penrose).
        - All numerical behaviour is delegated to `rim_os_v2.audit_file`.

    Args:
        file_path: Absolute path to the binary file to audit.
        prev_state: Optional previous ledger state hash. When provided, the
            resulting `ledger.next_state_hash` will extend the existing chain.

    Returns:
        The full RIM-OS audit report dictionary as returned by `audit_file`.

    Raises:
        RuntimeError: If the reported schema or genesis frame hash do not
            match the expected values derived from `GENESIS`.
    """
    if chain_seed is None:
        try:
            from app.services.artifact_chain import get_chain_seed as _get_chain_seed

            chain_seed = _get_chain_seed()
        except Exception:
            chain_seed = None

    t_start = time.time()
    try:
        report = audit_file(
            file_path,
            genesis=GENESIS,
            prev_state=prev_state,
            chain_seed=chain_seed,
            progress_callback=progress_callback,
        )
    except TypeError:
        # Backward compatibility for tests/mocks that stub audit_file without chain_seed.
        report = audit_file(
            file_path,
            genesis=GENESIS,
            prev_state=prev_state,
            progress_callback=progress_callback,
        )
    audit_time = time.time() - t_start

    # Lightweight performance telemetry for client transparency.
    inp = report.get("input", {}) or {}
    size_bytes = int(inp.get("size_bytes", 0) or 0)
    chunk_count = int(inp.get("chunk_count", 0) or 0)
    avg_chunk_time = audit_time / chunk_count if chunk_count else 0.0

    size_mb = size_bytes / (1024 * 1024)
    logger.info(
        "RIM-OS audit completed: size=%d bytes, chunks=%d, audit_time=%.3f s, avg_chunk_time=%.4f s",
        size_bytes,
        chunk_count,
        audit_time,
        avg_chunk_time,
    )
    logger.info(
        "Artifact size: %.1f MB | Chunks: %d | Audit time: %.2f seconds | Avg chunk time: %.3f seconds",
        size_mb,
        chunk_count,
        audit_time,
        avg_chunk_time,
    )

    schema = report.get("schema")
    if schema != EXPECTED_SCHEMA:
        raise RuntimeError(
            f"RIM-OS schema mismatch: expected '{EXPECTED_SCHEMA}', got '{schema}'"
        )

    frame_hash = report.get("genesis_frame_hash")
    if not frame_hash:
        frame_hash = (report.get("genesis", {}) or {}).get("frame_hash")
    if frame_hash != GENESIS_FRAME_HASH:
        # Hard failure: mixing Genesis frames would break the ledger.
        raise RuntimeError("Genesis frame mismatch")

    return report


def extract_kpis_from_report(report: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract high-level KPIs from a raw RIM-OS audit report.

    This helper provides a stable, backend-facing mapping from the client's
    canonical report structure into the subset of fields required by RIMOS:

        - integrity_score_0_100 → audit_score
        - risk_level            → risk
        - anomaly_fraction      → anomaly_fraction
        - avg_kag_separability  → kag_score
        - avg_penrose_match     → penrose_match
        - next_state_hash       → ledger_anchor
        - audit_content_sha256  → file_identity

    The mapping is intentionally shallow: the RIM-OS report format remains the
    source of truth, and this function should only adapt field names for
    UI/compliance/business-logic layers.
    """
    summary: Dict[str, Any] = report.get("summary", {}) or {}
    ledger: Dict[str, Any] = report.get("ledger", {}) or {}
    integrity: Dict[str, Any] = report.get("integrity", {}) or {}

    return {
        "audit_score": summary.get("integrity_score_0_100"),
        "risk": summary.get("risk_level"),
        "anomaly_fraction": summary.get("anomaly_fraction"),
        "kag_score": summary.get("avg_kag_separability"),
        "penrose_match": summary.get("avg_penrose_match"),
        "ledger_anchor": ledger.get("next_state_hash"),
        "file_identity": integrity.get("audit_content_sha256"),
    }

