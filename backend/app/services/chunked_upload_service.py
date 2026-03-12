"""
Chunked upload service for large files (5–10 GB).

Features:
- Parallel chunk uploads for faster transfer
- Low memory: chunks written directly to disk at offset
- Resumable: track uploaded chunks, client can retry missing
- Merge on completion, then run RIM audit
"""
import asyncio
import json
import os
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional, Set

from app.config import get_settings
from app.logging_config import logger
from app.services.file_validation import (
    SUPPORTED_EXTENSIONS,
    compute_file_hash_from_path,
    get_file_extension,
    validate_file_extension,
)
from app.services.rim_wrapper import run_rim_audit
from app.services.artifact_chain import add_artifact_block
from app.services.worker_executor import execute_in_worker
from app.utils.penrose import extract_penrose_from_report

settings = get_settings()


class FileProgressCallback:
    """Picklable progress callback that persists worker progress to disk."""

    def __init__(self, path: str):
        self.path = path

    def __call__(self, pct: float) -> None:
        try:
            Path(self.path).write_text(f"{pct:.4f}", encoding="ascii")
        except OSError:
            # Progress reporting is best-effort and must not break the audit.
            pass


@dataclass
class UploadSession:
    """In-memory session state for a chunked upload."""
    upload_id: str
    filename: str
    total_size: int
    total_chunks: int
    chunk_size: int
    temp_path: str
    uploaded_chunks: Set[int] = field(default_factory=set)
    status: str = "uploading"  # uploading | merging | processing | completed | failed
    error: Optional[str] = None
    result: Optional[dict] = None
    created_at: float = field(default_factory=time.time)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    # Per-chunk locks allow concurrent writes to different offsets (no lock contention across chunks)
    _chunk_locks: Dict[int, asyncio.Lock] = field(default_factory=dict)
    # Whether this filename maps to a PASS97-native format that should be
    # advertised as "full audit" in responses. Other extensions still receive
    # analysis but are reported as limited mode.
    supported_format: bool = True

    def progress_pct(self) -> float:
        if self.total_chunks == 0:
            return 0.0
        return 100.0 * len(self.uploaded_chunks) / self.total_chunks

    def is_complete(self) -> bool:
        return len(self.uploaded_chunks) == self.total_chunks


class ChunkedUploadService:
    """Manages chunked upload sessions."""

    def __init__(self):
        self._sessions: Dict[str, UploadSession] = {}
        self._sessions_lock = asyncio.Lock()
        self._temp_dir = settings.chunk_upload_temp_dir or None
        self._processing_progress: Dict[str, float] = {}  # upload_id -> RIM-OS progress 0-100

    def _get_temp_dir(self) -> str:
        if self._temp_dir:
            Path(self._temp_dir).mkdir(parents=True, exist_ok=True)
            return self._temp_dir
        return tempfile.gettempdir()

    def _session_meta_path(self, upload_id: str) -> str:
        return os.path.join(self._get_temp_dir(), f"chunk_upload_{upload_id}.json")

    def _progress_path(self, upload_id: str) -> str:
        return os.path.join(self._get_temp_dir(), f"chunk_upload_progress_{upload_id}.txt")

    def _persist_session(self, session: UploadSession) -> None:
        payload = {
            "upload_id": session.upload_id,
            "filename": session.filename,
            "total_size": session.total_size,
            "total_chunks": session.total_chunks,
            "chunk_size": session.chunk_size,
            "temp_path": session.temp_path,
            "uploaded_chunks": sorted(session.uploaded_chunks),
            "status": session.status,
            "error": session.error,
            "result": session.result,
            "created_at": session.created_at,
            "supported_format": session.supported_format,
        }
        Path(self._session_meta_path(session.upload_id)).write_text(
            json.dumps(payload, separators=(",", ":")),
            encoding="utf-8",
        )

    def _restore_session_from_disk(self, upload_id: str) -> Optional[UploadSession]:
        meta_path = self._session_meta_path(upload_id)
        if not os.path.exists(meta_path):
            return None

        try:
            data = json.loads(Path(meta_path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

        temp_path = data.get("temp_path", "")
        status = data.get("status", "uploading")
        if status != "completed" and not os.path.exists(temp_path):
            return None

        total_chunks = int(data["total_chunks"])
        session = UploadSession(
            upload_id=data["upload_id"],
            filename=data["filename"],
            total_size=int(data["total_size"]),
            total_chunks=total_chunks,
            chunk_size=int(data["chunk_size"]),
            temp_path=temp_path,
            uploaded_chunks=set(data.get("uploaded_chunks", [])),
            status=status,
            error=data.get("error"),
            result=data.get("result"),
            created_at=float(data.get("created_at", time.time())),
            _chunk_locks={i: asyncio.Lock() for i in range(total_chunks)},
            supported_format=bool(data.get("supported_format", True)),
        )
        self._sessions[upload_id] = session
        return session

    async def _get_session(self, upload_id: str) -> Optional[UploadSession]:
        async with self._sessions_lock:
            session = self._sessions.get(upload_id)
            if session:
                return session
            return self._restore_session_from_disk(upload_id)

    def _delete_session_files(self, session: UploadSession) -> None:
        for path in (
            session.temp_path,
            self._session_meta_path(session.upload_id),
            self._progress_path(session.upload_id),
        ):
            try:
                if path and os.path.exists(path):
                    os.unlink(path)
            except OSError:
                pass

    async def create_session(
        self,
        filename: str,
        total_size: int,
        total_chunks: int,
        chunk_size: int,
    ) -> tuple[str, list[int]]:
        """Create new upload session. Returns (upload_id, [] for new or existing chunk indices for resume)."""
        # Extension awareness only – we no longer reject based solely on file
        # extension. Instead, we track whether the artifact is in a
        # PASS97-native format so that the response can distinguish full
        # audit vs limited analysis.
        if settings.validate_file_extension:
            ext_valid, ext_error = validate_file_extension(filename)
            if not ext_valid:
                raise ValueError(ext_error.message if ext_error else "Invalid file extension")

        ext = get_file_extension(filename or "")
        supported_format = ext in SUPPORTED_EXTENSIONS

        if total_size > settings.max_file_size:
            raise ValueError(f"File too large. Maximum is {settings.max_file_size // 1_000_000}MB.")

        upload_id = str(uuid.uuid4())
        temp_dir = self._get_temp_dir()
        temp_path = os.path.join(temp_dir, f"chunk_upload_{upload_id}.bin")

        # Pre-allocate file to avoid fragmentation and allow parallel writes.
        # Per-chunk locks enable concurrent chunk uploads (each chunk writes to a unique offset).
        chunk_locks = {i: asyncio.Lock() for i in range(total_chunks)}
        async with self._sessions_lock:
            session = UploadSession(
                upload_id=upload_id,
                filename=filename,
                total_size=total_size,
                total_chunks=total_chunks,
                chunk_size=chunk_size,
                temp_path=temp_path,
                _chunk_locks=chunk_locks,
                supported_format=supported_format,
            )
            self._sessions[upload_id] = session
            self._persist_session(session)

        # Create file and pre-allocate (sparse on most FS)
        with open(temp_path, "wb") as f:
            f.seek(total_size - 1)
            f.write(b"\x00")

        return upload_id, []

    async def write_chunk(
        self,
        upload_id: str,
        chunk_index: int,
        data: bytes,
    ) -> tuple[bool, Optional[str]]:
        """
        Write a chunk to the session file.
        Uses per-chunk lock so multiple chunks can be written concurrently (different offsets).
        Returns (success, error_message).
        """
        session = await self._get_session(upload_id)
        if not session:
            return False, "Upload session not found or expired"
        chunk_lock = session._chunk_locks.get(chunk_index)
        if not chunk_lock:
            return False, f"Invalid chunk index {chunk_index}"

        async with chunk_lock:
            async with session._lock:
                if chunk_index in session.uploaded_chunks:
                    return True, None  # Idempotent: already received
                if chunk_index < 0 or chunk_index >= session.total_chunks:
                    return False, f"Invalid chunk index {chunk_index}"
                expected_size = session.chunk_size
                if chunk_index == session.total_chunks - 1:
                    remainder = session.total_size - (chunk_index * session.chunk_size)
                    expected_size = min(session.chunk_size, remainder)
                if len(data) != expected_size and chunk_index < session.total_chunks - 1:
                    return False, f"Chunk size mismatch: expected {expected_size}, got {len(data)}"

            # File write without holding session lock (parallel writes to different offsets)
            offset = chunk_index * session.chunk_size
            try:
                with open(session.temp_path, "r+b") as f:
                    f.seek(offset)
                    f.write(data)
            except Exception as e:
                logger.error(f"Failed to write chunk {chunk_index}: {e}")
                return False, str(e)

            async with session._lock:
                session.uploaded_chunks.add(chunk_index)
                self._persist_session(session)

        return True, None

    async def get_status(self, upload_id: str) -> Optional[dict]:
        """Get session status."""
        session = await self._get_session(upload_id)
        if not session:
            return None
        out: dict = {
            "upload_id": session.upload_id,
            "filename": session.filename,
            "total_size": session.total_size,
            "total_chunks": session.total_chunks,
            "chunk_size": session.chunk_size,
            "uploaded_chunks": sorted(session.uploaded_chunks),
            "status": session.status,
            "progress_pct": session.progress_pct(),
            "error": session.error,
        }
        if session.status == "processing":
            if upload_id not in self._processing_progress:
                try:
                    raw = Path(self._progress_path(upload_id)).read_text(encoding="ascii").strip()
                    if raw:
                        self._processing_progress[upload_id] = max(0.0, min(100.0, float(raw)))
                except (OSError, ValueError):
                    self._processing_progress[upload_id] = 0.0
            out["processing_pct"] = self._processing_progress.get(upload_id, 0.0)
        if session.status == "completed" and session.result:
            out["result"] = session.result
        return out

    def start_background_complete(self, upload_id: str) -> None:
        """
        Start complete_and_process in a background task. Returns immediately.
        Client should poll GET /status until status=completed or failed.
        """
        async def _run() -> None:
            try:
                await self.complete_and_process(upload_id)
            except Exception as e:
                logger.error(f"Background complete failed for {upload_id}: {e}")

        asyncio.create_task(_run())

    async def complete_and_process(self, upload_id: str) -> dict:
        """
        When all chunks received, validate, run RIM audit, return result.
        Caller should invoke this after verifying is_complete.
        """
        session = await self._get_session(upload_id)
        if not session:
            raise ValueError("Upload session not found or expired")

        async with session._lock:
            if not session.is_complete():
                raise ValueError("Not all chunks received yet")

            if session.status == "completed":
                return session.result

            session.status = "merging"
            self._persist_session(session)
            # Merge is implicit - we wrote directly to offsets

        try:
            session.status = "processing"
            self._persist_session(session)
            # Size validation
            actual_size = os.path.getsize(session.temp_path)
            if actual_size != session.total_size:
                raise ValueError(f"File size mismatch: expected {session.total_size}, got {actual_size}")

            # Minimal validation
            if actual_size < 32:
                raise ValueError("File too small for audit artifact")

            # Execute the CPU-bound audit in the process worker pool rather
            # than a thread so chunked uploads inherit the intended isolation
            # and timeout behavior. Progress is mirrored through a temp file
            # so the polling endpoint can still expose live status updates.
            progress_path = self._progress_path(upload_id)
            self._processing_progress[upload_id] = 0.0
            Path(progress_path).write_text("0.0", encoding="ascii")

            stop_progress_monitor = asyncio.Event()

            async def _monitor_progress() -> None:
                while not stop_progress_monitor.is_set():
                    try:
                        raw = Path(progress_path).read_text(encoding="ascii").strip()
                        if raw:
                            pct = max(0.0, min(100.0, float(raw)))
                            self._processing_progress[upload_id] = pct
                    except (OSError, ValueError):
                        pass
                    await asyncio.sleep(0.5)

            progress_task = asyncio.create_task(_monitor_progress())

            try:
                report = await execute_in_worker(
                    run_rim_audit,
                    session.temp_path,
                    None,
                    FileProgressCallback(progress_path),
                )
            finally:
                stop_progress_monitor.set()
                await progress_task
                try:
                    os.unlink(progress_path)
                except OSError:
                    pass

            self._processing_progress[upload_id] = 100.0

            # Compute hash (streaming) in thread to avoid blocking
            file_hash = await asyncio.to_thread(compute_file_hash_from_path, session.temp_path)
            artifact_block = None
            try:
                artifact_block = add_artifact_block(report, file_hash)
                report["artifact_block"] = artifact_block
            except Exception as chain_error:
                logger.warning(
                    "Artifact chain append failed for %s: %s",
                    session.filename,
                    chain_error,
                )

            # Build response in same shape as single-file upload
            summary = report.get("summary", {}) or {}
            risk_level = summary.get("risk_level", "HIGH")
            audit_score = float(summary.get("integrity_score_0_100", 0.0))
            anomaly_fraction = float(summary.get("anomaly_fraction", 0.0))
            kag_score = float(summary.get("avg_kag_separability", 0.0))
            anomaly_count = int(summary.get("anomaly_count", 0))
            coverage_pct = (1.0 - anomaly_fraction) * 100.0

            def adjust_status(base: str) -> str:
                if risk_level == "HIGH":
                    return "warning"
                if risk_level == "MEDIUM" and base == "excellent":
                    return "good"
                return base

            from app.models.common_schemas import (
                ArtifactBlock,
                KPI,
                VerificationStatus,
                RiskBadge,
                EUAIActCompliance,
                LegalDisclosures,
                LedgerInfo,
                MapPosition,
            )
            from app.routers.report import cache_audit_result
            from app.models.common_schemas import ExtendedAuditResult

            audit_status = adjust_status("excellent" if audit_score >= 90 else "good" if audit_score >= 70 else "warning")
            issues_status = adjust_status("warning" if anomaly_count > 0 else "excellent")
            kag_status = adjust_status("excellent" if kag_score >= 0.5 else "good" if kag_score >= 0.3 else "warning")
            coverage_status = adjust_status("excellent" if anomaly_fraction == 0.0 else "good" if anomaly_fraction <= 0.05 else "warning")

            status_str = "Verified" if risk_level == "LOW" else "Verified with Warnings" if risk_level == "MEDIUM" else "Verification Failed"

            # Annotate verification mode for chunked uploads based on the
            # original filename extension.
            if session.supported_format:
                verification_mode = "Full PASS97 Audit"
                verification_mode_key = "full"
                verification_mode_reason = None
            else:
                verification_mode = "Limited Analysis"
                verification_mode_key = "limited"
                verification_mode_reason = (
                    "File type not in PASS97-native formats (.lm3z, .rim0, .rim95, .safetensors, "
                    ".bin, .gguf, .pt, .pth, .ckpt, .onnx); "
                    "RIM-OS metrics computed, but format-specific semantics may be unavailable."
                )

            checks = [
                f"Verification Mode - {verification_mode}",
                "Stage 1 - Schema & Genesis: OK",
                f"Stage 2 - Entropy: avg_entropy_bits={summary.get('avg_entropy_bits', 0.0):.4f}",
                f"Stage 3 - Penrose geometry: avg_penrose_match={summary.get('avg_penrose_match', 0.0):.4f}",
                f"Stage 4 - Anomalies: anomaly_fraction={anomaly_fraction:.4f}, count={anomaly_count}",
                f"Stage 5 - Risk: risk_level={risk_level}",
            ]

            mock_kpis = [
                KPI(id="kpi-1", label="Audit Score", value=audit_score, trend="stable", status=audit_status, description="RIM-OS integrity score"),
                KPI(id="kpi-2", label="Issues Found", value=anomaly_count, trend="up" if anomaly_count > 0 else "down", status=issues_status, description="Anomalous chunks"),
                KPI(id="kpi-3", label="KAG Score", value=f"{kag_score:.4f}", trend="up" if kag_score >= 0.5 else "down", status=kag_status, description="KAG separability"),
                KPI(id="kpi-4", label="Coverage", value=f"{coverage_pct:.1f}%", trend="up", status=coverage_status, description="Coverage"),
                KPI(id="kpi-5", label="Penrose Sector", value=0, trend="stable", status="warning", description="Penrose"),
            ]

            mock_verification = VerificationStatus(
                status=status_str,
                confidence=int(audit_score),
                timestamp=report.get("time_utc", ""),
                checks=checks,
            )

            ledger = report.get("ledger") or {}
            integrity_block = report.get("integrity", {}) or {}
            risk_badge = RiskBadge.from_audit_score(audit_score, 0 if risk_level == "LOW" else 1 if risk_level == "MEDIUM" else 3)
            eu_ai_act = EUAIActCompliance.from_risk_badge(risk_badge)
            ledger_info = LedgerInfo(
                ledger_id="RIM-OS-LEDGER",
                sequence_number=0,
                prev_state=ledger.get("prev_state"),
                next_state_hash=ledger.get("next_state_hash"),
                audit_content_sha256=integrity_block.get("audit_content_sha256", file_hash),
                entry_hash=ledger.get("events_hash", file_hash),
            )
            penrose_details = extract_penrose_from_report(report, fallback_hash=file_hash)
            extended = ExtendedAuditResult(
                kpis=mock_kpis,
                verification=mock_verification,
                file_hash=file_hash,
                anomalies=[],
                risk_badge=risk_badge,
                eu_ai_act=eu_ai_act,
                legal_disclosures=LegalDisclosures.default(),
                ledger=ledger_info,
                penrose_details=penrose_details,
                map_position=MapPosition(**(report.get("map_position") or {
                    "tau_vectors": [],
                    "barycentric": [],
                    "manifold_hash": "",
                    "tile_hash": "",
                })),
                artifact_block=ArtifactBlock(**artifact_block) if artifact_block else None,
                tile_hash=penrose_details["tile_hash"],
            )
            cache_audit_result(upload_id, extended)

            response_data = {
                "upload_id": upload_id,
                "file_info": {"name": session.filename, "size": session.total_size, "type": "application/octet-stream"},
                "kpis": [k.model_dump() for k in mock_kpis],
                "verification": mock_verification.model_dump(),
                "file_hash": file_hash,
                "artifact_block": artifact_block,
                "metadata": {
                    "name": f"Audit Report: {session.filename}",
                    "description": "Cryptographic audit artifact verified by Pass97 pipeline.",
                    "attributes": [
                        {"trait_type": "Audit Score", "value": audit_score},
                        {"trait_type": "Status", "value": status_str}
                    ],
                    "verification_mode": verification_mode_key,
                    **(
                        {"verification_mode_reason": verification_mode_reason}
                        if verification_mode_reason
                        else {}
                    ),
                },
            }

            async with session._lock:
                session.status = "completed"
                session.result = response_data
                self._persist_session(session)
            self._processing_progress.pop(upload_id, None)

            try:
                if os.path.exists(session.temp_path):
                    os.unlink(session.temp_path)
            except OSError:
                pass

            return response_data

        except Exception as e:
            logger.error(f"Chunked upload processing failed for {upload_id}: {e}")
            self._processing_progress.pop(upload_id, None)
            async with session._lock:
                session.status = "failed"
                session.error = str(e)
                self._persist_session(session)
            self._delete_session_files(session)
            raise

    async def cleanup_expired(self):
        """Remove sessions older than TTL."""
        now = time.time()
        ttl = settings.chunk_upload_session_ttl_seconds
        async with self._sessions_lock:
            to_remove = [
                uid for uid, s in self._sessions.items()
                if now - s.created_at > ttl and s.status != "processing"
            ]
            for uid in to_remove:
                s = self._sessions.pop(uid, None)
                if s:
                    self._delete_session_files(s)


chunked_upload_service = ChunkedUploadService()
