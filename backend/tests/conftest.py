"""
Pytest configuration and fixtures for RIMOS backend tests.
"""
import hashlib
import json
import os
import struct

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    """FastAPI test client fixture."""
    return TestClient(app)


@pytest.fixture
def sample_valid_content() -> bytes:
    """Generate content that passes all pipeline stages."""
    # 1024 bytes of varied content to ensure high entropy and diversity
    return bytes(range(256)) * 4


@pytest.fixture
def sample_invalid_content() -> bytes:
    """Generate content that fails validation."""
    return b"236"


def make_file(name: str, content: bytes):
    """Helper to create a file tuple for upload."""
    return {"file": (name, content, "application/octet-stream")}


# ─── New Fixtures for Milestone 1 ────────────────────────────────────────────

@pytest.fixture
def sample_lm3z_content() -> bytes:
    """Generate valid .lm3z format content with metadata header."""
    # LM3Z format:
    # - Bytes 0-3: Magic "LM3Z"
    # - Bytes 4-7: Header size (uint32 LE)
    # - Bytes 8-11: Payload size (uint32 LE)
    # - Bytes 12-43: Public key (32 bytes)
    # - Bytes 44-107: Signature (64 bytes)
    # - Bytes 108-header_size: JSON metadata
    # - Remaining: Binary payload
    
    payload = bytes(range(256)) * 4  # 1024 bytes payload
    public_key = bytes(range(32))  # Dummy public key
    signature = bytes(range(64))  # Dummy signature
    
    json_metadata = json.dumps({
        "version": "1.0",
        "artifact_id": "test-artifact-001",
        "author": "Test Author"
    }).encode()
    
    header_size = 108 + len(json_metadata)
    
    # Build header
    header = b"LM3Z"
    header += struct.pack("<I", header_size)  # header_size
    header += struct.pack("<I", len(payload))  # payload_size
    header += public_key  # 32 bytes
    header += signature  # 64 bytes
    header += json_metadata
    
    return header + payload


@pytest.fixture
def sample_rim0_content() -> bytes:
    """Generate valid .rim0 format content with metadata header."""
    # RIM0 format:
    # - Bytes 0-3: Magic "RIM0"
    # - Bytes 4-5: Version (uint16 LE)
    # - Bytes 6-7: Flags (uint16 LE)
    # - Bytes 8-11: Key offset (uint32 LE)
    # - Bytes 12-15: Signature offset (uint32 LE)
    # - Bytes 16-19: Payload offset (uint32 LE)
    # - Bytes 20-23: Payload size (uint32 LE)
    # - Variable: Public key (32 bytes at key_offset)
    # - Variable: Signature (64 bytes at sig_offset)
    # - Variable: Payload (at payload_offset)
    
    payload = bytes(range(256)) * 4  # 1024 bytes payload
    public_key = bytes(range(32))  # Dummy public key
    signature = bytes(range(64))  # Dummy signature
    
    key_offset = 24
    sig_offset = key_offset + 32
    payload_offset = sig_offset + 64
    
    # Build header
    header = b"RIM0"
    header += struct.pack("<H", 1)  # version
    header += struct.pack("<H", 0)  # flags
    header += struct.pack("<I", key_offset)
    header += struct.pack("<I", sig_offset)
    header += struct.pack("<I", payload_offset)
    header += struct.pack("<I", len(payload))
    header += public_key
    header += signature
    
    return header + payload


@pytest.fixture
def sample_rim95_content() -> bytes:
    """Generate valid .rim95 format content with metadata header."""
    # RIM95 format:
    # - Bytes 0-3: Magic "R95\x00"
    # - Bytes 4-7: JSON metadata size (uint32 LE)
    # - Bytes 8-39: Public key (32 bytes)
    # - Bytes 40-103: Signature (64 bytes)
    # - Bytes 104-(104+json_size): JSON metadata
    # - Remaining: Binary payload
    
    payload = bytes(range(256)) * 4  # 1024 bytes payload
    public_key = bytes(range(32))  # Dummy public key
    signature = bytes(range(64))  # Dummy signature
    
    json_metadata = json.dumps({
        "version": "95.0",
        "artifact_id": "test-rim95-001",
        "author": "Test Author"
    }).encode()
    
    # Build header
    header = b"R95\x00"
    header += struct.pack("<I", len(json_metadata))
    header += public_key
    header += signature
    header += json_metadata
    
    return header + payload


@pytest.fixture
def signed_payload_fixture():
    """Generate a properly signed payload for signature verification tests."""
    try:
        from nacl.signing import SigningKey
        
        # Generate keypair
        signing_key = SigningKey.generate()
        verify_key = signing_key.verify_key
        
        # Create payload
        payload = bytes(range(256)) * 4
        
        # Sign payload
        signed = signing_key.sign(payload)
        
        return {
            "payload": payload,
            "signature": signed.signature,
            "public_key": bytes(verify_key),
            "private_key": bytes(signing_key)
        }
    except ImportError:
        pytest.skip("pynacl not installed")


@pytest.fixture(autouse=True)
def clear_abuse_stores():
    """Clear abuse protection stores before and after each test."""
    from app.services.abuse_protection import clear_stores
    clear_stores()
    yield
    clear_stores()


@pytest.fixture(autouse=True)
def reset_settings_cache():
    """Reset settings cache before each test to ensure clean state."""
    from app.config import get_settings
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def isolate_artifact_chain_path(monkeypatch, tmp_path):
    """Give each test an isolated local artifact chain file."""
    monkeypatch.setenv("ARTIFACT_CHAIN_PATH", str(tmp_path / "artifact_chain.json"))


@pytest.fixture(autouse=True)
def isolate_report_cache_dir(monkeypatch, tmp_path):
    """Give each test an isolated persistent report cache directory."""
    monkeypatch.setenv("REPORT_CACHE_DIR", str(tmp_path / "report_cache"))


@pytest.fixture
def disable_abuse_protection(monkeypatch):
    """Disable abuse protection for tests that need multiple uploads."""
    from app import config
    
    original_settings = config.Settings()
    
    class TestSettings(config.Settings):
        enable_deduplication: bool = False
        enable_replay_detection: bool = False
    
    test_settings = TestSettings()
    monkeypatch.setattr(config, "get_settings", lambda: test_settings)
    yield test_settings


@pytest.fixture
def disable_extensions_fixture(monkeypatch):
    """Fixture to disable extension validation for backward compatibility tests."""
    from app import config
    
    class MockSettings:
        def __init__(self, original):
            self._original = original
            
        def __getattr__(self, name):
            if name == "validate_file_extension":
                return False
            return getattr(self._original, name)
    
    original_settings = config.get_settings()
    monkeypatch.setattr(
        config, 
        "get_settings", 
        lambda: MockSettings(original_settings)
    )

