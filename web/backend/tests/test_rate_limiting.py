"""
Tests for rate limiting and abuse protection.
These tests verify the ADDITIVE abuse protection functionality.
"""
import time

import pytest

from app.services.abuse_protection import (
    DeduplicationStore,
    check_duplicate,
    check_replay,
    compute_dedup_key,
    compute_replay_key,
    record_upload,
    clear_stores,
    get_client_ip,
)


# ─── DeduplicationStore Tests ────────────────────────────────────────────────

def test_deduplication_store_add():
    """Should add and detect keys."""
    store = DeduplicationStore(max_entries=100, ttl_seconds=3600)
    
    result = store.add("key1")
    
    assert result is True
    assert store.exists("key1") is True


def test_deduplication_store_detect_duplicate():
    """Should detect duplicate keys."""
    store = DeduplicationStore(max_entries=100, ttl_seconds=3600)
    
    store.add("key1")
    result = store.add("key1")
    
    assert result is False


def test_deduplication_store_different_keys():
    """Should distinguish different keys."""
    store = DeduplicationStore(max_entries=100, ttl_seconds=3600)
    
    store.add("key1")
    store.add("key2")
    
    assert store.exists("key1") is True
    assert store.exists("key2") is True


def test_deduplication_store_remove():
    """Should remove keys."""
    store = DeduplicationStore(max_entries=100, ttl_seconds=3600)
    
    store.add("key1")
    store.remove("key1")
    
    assert store.exists("key1") is False


def test_deduplication_store_clear():
    """Should clear all keys."""
    store = DeduplicationStore(max_entries=100, ttl_seconds=3600)
    
    store.add("key1")
    store.add("key2")
    store.clear()
    
    assert store.exists("key1") is False
    assert store.exists("key2") is False


def test_deduplication_store_max_entries():
    """Should evict oldest entries when over limit."""
    store = DeduplicationStore(max_entries=3, ttl_seconds=3600)
    
    store.add("key1")
    store.add("key2")
    store.add("key3")
    store.add("key4")  # Should evict key1
    
    assert store.exists("key1") is False
    assert store.exists("key4") is True


# ─── Deduplication Function Tests ────────────────────────────────────────────

def test_compute_dedup_key():
    """Should compute consistent dedup keys."""
    content = b"test content"
    
    key1 = compute_dedup_key(content)
    key2 = compute_dedup_key(content)
    
    assert key1 == key2


def test_compute_dedup_key_with_ip():
    """Should include IP in dedup key when provided."""
    content = b"test content"
    
    key1 = compute_dedup_key(content, "192.168.1.1")
    key2 = compute_dedup_key(content, "192.168.1.2")
    
    assert key1 != key2


def test_check_duplicate_first_upload():
    """First upload should not be duplicate."""
    clear_stores()
    content = b"unique content"
    
    is_dup, error = check_duplicate(content)
    
    assert is_dup is False
    assert error is None


def test_check_duplicate_after_record():
    """Recorded upload should be detected as duplicate."""
    clear_stores()
    content = b"duplicate content"
    
    record_upload(content)
    is_dup, error = check_duplicate(content)
    
    assert is_dup is True
    assert error is not None
    assert error.code.value == "DUPLICATE_UPLOAD"


def test_check_duplicate_disabled():
    """Disabled deduplication should not detect duplicates."""
    clear_stores()
    content = b"test content"
    
    record_upload(content)
    is_dup, error = check_duplicate(content, enabled=False)
    
    assert is_dup is False
    assert error is None


# ─── Replay Detection Tests ──────────────────────────────────────────────────

def test_compute_replay_key():
    """Should compute consistent replay keys."""
    content = b"test content"
    ip = "192.168.1.1"
    timestamp = 1000000000
    
    key1 = compute_replay_key(content, ip, timestamp)
    key2 = compute_replay_key(content, ip, timestamp)
    
    assert key1 == key2


def test_compute_replay_key_different_time_buckets():
    """Keys should differ for different time buckets."""
    content = b"test content"
    ip = "192.168.1.1"
    
    key1 = compute_replay_key(content, ip, 1000000000)
    key2 = compute_replay_key(content, ip, 1000000400)  # Different 5-min bucket
    
    assert key1 != key2


def test_check_replay_first_request():
    """First request should not be replay."""
    clear_stores()
    
    is_replay, error = check_replay(b"content", "192.168.1.1")
    
    assert is_replay is False
    assert error is None


def test_check_replay_consecutive_requests():
    """Consecutive identical requests should be replay."""
    clear_stores()
    content = b"replay content"
    ip = "192.168.1.1"
    
    # First request
    is_replay1, _ = check_replay(content, ip)
    # Second request (same content, same IP, same time window)
    is_replay2, error = check_replay(content, ip)
    
    assert is_replay1 is False
    assert is_replay2 is True
    assert error.code.value == "REPLAY_DETECTED"


def test_check_replay_different_content():
    """Different content should not be replay."""
    clear_stores()
    ip = "192.168.1.1"
    
    check_replay(b"content1", ip)
    is_replay, error = check_replay(b"content2", ip)
    
    assert is_replay is False
    assert error is None


def test_check_replay_different_ip():
    """Same content from different IP should not be replay."""
    clear_stores()
    content = b"same content"
    
    check_replay(content, "192.168.1.1")
    is_replay, error = check_replay(content, "192.168.1.2")
    
    assert is_replay is False


def test_check_replay_disabled():
    """Disabled replay detection should not detect replays."""
    clear_stores()
    content = b"content"
    ip = "192.168.1.1"
    
    check_replay(content, ip, enabled=True)
    is_replay, error = check_replay(content, ip, enabled=False)
    
    assert is_replay is False


# ─── Clear Stores Tests ──────────────────────────────────────────────────────

def test_clear_stores():
    """clear_stores should reset all protection stores."""
    content = b"test content"
    
    record_upload(content)
    check_replay(content, "192.168.1.1")
    
    clear_stores()
    
    is_dup, _ = check_duplicate(content)
    is_replay, _ = check_replay(content, "192.168.1.1")
    
    assert is_dup is False
    assert is_replay is False
