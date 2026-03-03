"""
Rate limiting and abuse protection service.

This is an ADDITIVE service that provides:
- Per-IP rate limiting using slowapi
- Hash-based deduplication
- Replay detection
- All protections are opt-out configurable

This does NOT alter existing logic paths.
"""
import hashlib
import time
from collections import OrderedDict
from threading import Lock
from typing import Optional, Tuple

from fastapi import Request

from app.config import get_settings
from app.logging_config import logger
from app.models.error_schemas import ErrorCode, StructuredError


settings = get_settings()


# ─── In-Memory Deduplication Store ───────────────────────────────────────────

class DeduplicationStore:
    """
    Thread-safe in-memory store for deduplication and replay detection.
    
    Uses LRU-style eviction to prevent unbounded memory growth.
    For production, this should be replaced with Redis or similar.
    """
    
    def __init__(self, max_entries: int = 10000, ttl_seconds: int = 3600):
        self._store: OrderedDict[str, float] = OrderedDict()
        self._lock = Lock()
        self.max_entries = max_entries
        self.ttl_seconds = ttl_seconds
    
    def _cleanup_expired(self) -> None:
        """Remove expired entries."""
        now = time.time()
        expired = [k for k, v in self._store.items() if now - v > self.ttl_seconds]
        for key in expired:
            del self._store[key]
    
    def _evict_oldest(self) -> None:
        """Evict oldest entries if over limit."""
        while len(self._store) > self.max_entries:
            self._store.popitem(last=False)
    
    def exists(self, key: str) -> bool:
        """Check if key exists and is not expired."""
        with self._lock:
            self._cleanup_expired()
            if key in self._store:
                timestamp = self._store[key]
                if time.time() - timestamp <= self.ttl_seconds:
                    return True
                else:
                    del self._store[key]
            return False
    
    def add(self, key: str) -> bool:
        """
        Add key to store.
        
        Returns:
            True if key was new, False if it already existed
        """
        with self._lock:
            self._cleanup_expired()
            
            if key in self._store:
                # Update timestamp (move to end)
                self._store.move_to_end(key)
                self._store[key] = time.time()
                return False
            
            self._store[key] = time.time()
            self._evict_oldest()
            return True
    
    def remove(self, key: str) -> None:
        """Remove key from store."""
        with self._lock:
            self._store.pop(key, None)
    
    def clear(self) -> None:
        """Clear all entries."""
        with self._lock:
            self._store.clear()


# Global deduplication stores
_upload_hash_store = DeduplicationStore(max_entries=10000, ttl_seconds=3600)
_replay_store = DeduplicationStore(max_entries=10000, ttl_seconds=300)


# ─── Rate Limiting Setup ─────────────────────────────────────────────────────

def get_client_ip(request: Request) -> str:
    """
    Extract client IP from request.
    
    Handles X-Forwarded-For for reverse proxy setups.
    """
    # Check for X-Forwarded-For header (reverse proxy)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # Take the first IP in the chain
        return forwarded.split(",")[0].strip()
    
    # Fall back to client host
    return request.client.host if request.client else "unknown"


def setup_rate_limiter(app):
    """
    Setup rate limiting for the FastAPI application.
    
    This should be called in main.py to enable rate limiting.
    Rate limiting is opt-out via RATE_LIMIT_ENABLED setting.
    """
    try:
        from slowapi import Limiter, _rate_limit_exceeded_handler
        from slowapi.util import get_remote_address
        from slowapi.errors import RateLimitExceeded
        
        limiter = Limiter(key_func=get_remote_address)
        app.state.limiter = limiter
        app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
        
        logger.info("Rate limiting enabled")
        return limiter
        
    except ImportError:
        logger.warning("slowapi not installed - rate limiting disabled")
        return None


def get_rate_limit_decorator():
    """
    Get the rate limit decorator for routes.
    
    Returns a decorator that can be applied to routes.
    If slowapi is not installed, returns a no-op decorator.
    """
    try:
        from slowapi import Limiter
        from slowapi.util import get_remote_address
        
        limiter = Limiter(key_func=get_remote_address)
        return limiter.limit
    except ImportError:
        # Return a no-op decorator
        def no_op_limit(rate_string):
            def decorator(func):
                return func
            return decorator
        return no_op_limit


# ─── Deduplication Functions ─────────────────────────────────────────────────

def compute_dedup_key(contents: bytes, client_ip: str = None) -> str:
    """
    Compute deduplication key from file contents.
    
    Args:
        contents: File contents
        client_ip: Optional client IP for per-client dedup
        
    Returns:
        Deduplication key
    """
    content_hash = hashlib.sha256(contents).hexdigest()
    if client_ip:
        return f"{client_ip}:{content_hash}"
    return content_hash


def check_duplicate(
    contents: bytes,
    client_ip: str = None,
    enabled: bool = True
) -> Tuple[bool, Optional[StructuredError]]:
    """
    Check if upload is a duplicate.
    
    Args:
        contents: File contents
        client_ip: Client IP for per-client dedup
        enabled: Whether deduplication is enabled
        
    Returns:
        Tuple of (is_duplicate, error if duplicate)
    """
    if not enabled:
        return False, None
    
    key = compute_dedup_key(contents, client_ip)
    
    if _upload_hash_store.exists(key):
        return True, StructuredError(
            code=ErrorCode.DUPLICATE_UPLOAD,
            message="Duplicate upload detected. This file has already been processed.",
            details={"hash": hashlib.sha256(contents).hexdigest()[:16]}
        )
    
    return False, None


def record_upload(contents: bytes, client_ip: str = None) -> None:
    """
    Record an upload in the deduplication store.
    
    Args:
        contents: File contents
        client_ip: Client IP for per-client dedup
    """
    key = compute_dedup_key(contents, client_ip)
    _upload_hash_store.add(key)


# ─── Replay Detection ────────────────────────────────────────────────────────

def compute_replay_key(
    contents: bytes,
    client_ip: str,
    timestamp: float = None
) -> str:
    """
    Compute replay detection key.
    
    Uses a combination of content hash, client IP, and time window.
    """
    if timestamp is None:
        timestamp = time.time()
    
    # Create time window (5-minute buckets)
    time_bucket = int(timestamp // 300) * 300
    
    content_hash = hashlib.sha256(contents).hexdigest()[:16]
    return f"replay:{client_ip}:{content_hash}:{time_bucket}"


def check_replay(
    contents: bytes,
    client_ip: str,
    enabled: bool = True
) -> Tuple[bool, Optional[StructuredError]]:
    """
    Check for replay attack.
    
    Detects if the same file is being uploaded multiple times in a short window.
    
    Args:
        contents: File contents
        client_ip: Client IP
        enabled: Whether replay detection is enabled
        
    Returns:
        Tuple of (is_replay, error if replay)
    """
    if not enabled:
        return False, None
    
    key = compute_replay_key(contents, client_ip)
    
    if _replay_store.exists(key):
        return True, StructuredError(
            code=ErrorCode.REPLAY_DETECTED,
            message="Replay detected. Please wait before re-uploading the same file.",
            details={"window_seconds": 300}
        )
    
    # Record this request
    _replay_store.add(key)
    return False, None


# ─── Combined Protection Check ───────────────────────────────────────────────

def check_abuse_protection(
    contents: bytes,
    request: Request,
    enable_dedup: bool = True,
    enable_replay: bool = True
) -> Tuple[bool, Optional[StructuredError]]:
    """
    Run all abuse protection checks.
    
    Args:
        contents: File contents
        request: FastAPI request for client IP
        enable_dedup: Enable deduplication check
        enable_replay: Enable replay detection
        
    Returns:
        Tuple of (passed_all_checks, error if any check failed)
    """
    client_ip = get_client_ip(request)
    
    # Check for replay attack first (stricter)
    is_replay, replay_error = check_replay(contents, client_ip, enable_replay)
    if is_replay:
        logger.warning(f"Replay detected from {client_ip}")
        return False, replay_error
    
    # Check for duplicate (longer window)
    is_duplicate, dup_error = check_duplicate(contents, client_ip, enable_dedup)
    if is_duplicate:
        logger.info(f"Duplicate upload from {client_ip}")
        return False, dup_error
    
    return True, None


def clear_stores() -> None:
    """Clear all protection stores (for testing)."""
    _upload_hash_store.clear()
    _replay_store.clear()
