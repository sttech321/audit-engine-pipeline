"""
Tests for Ed25519 signature verification.
These tests verify the ADDITIVE cryptographic verification functionality.
"""
import hashlib

import pytest

from app.services.signature_verification import (
    SignatureVerificationResult,
    verify_signature,
    verify_artifact_signature,
    generate_test_keypair,
    sign_payload,
)


# ─── Skip if pynacl not installed ────────────────────────────────────────────

try:
    import nacl
    PYNACL_AVAILABLE = True
except ImportError:
    PYNACL_AVAILABLE = False

pytestmark = pytest.mark.skipif(not PYNACL_AVAILABLE, reason="pynacl not installed")


# ─── Basic Signature Verification Tests ──────────────────────────────────────

def test_verify_valid_signature():
    """Should verify a valid signature."""
    private_key, public_key = generate_test_keypair()
    payload = b"test payload data"
    signature = sign_payload(payload, private_key)
    
    result = verify_signature(payload, signature, public_key)
    
    assert result.verified is True
    assert result.error_code is None
    assert result.computed_hash is not None


def test_verify_invalid_signature():
    """Should reject an invalid signature."""
    private_key, public_key = generate_test_keypair()
    payload = b"test payload data"
    
    # Create a fake signature
    fake_signature = bytes(64)
    
    result = verify_signature(payload, fake_signature, public_key)
    
    assert result.verified is False
    assert result.error_code is not None


def test_verify_tampered_payload():
    """Should reject signature when payload has been tampered."""
    private_key, public_key = generate_test_keypair()
    original_payload = b"original payload data"
    signature = sign_payload(original_payload, private_key)
    
    tampered_payload = b"tampered payload data"
    
    result = verify_signature(tampered_payload, signature, public_key)
    
    assert result.verified is False
    assert "SIGNATURE_VERIFICATION_FAILED" in result.error_code


def test_verify_wrong_public_key():
    """Should reject signature with wrong public key."""
    private_key1, public_key1 = generate_test_keypair()
    private_key2, public_key2 = generate_test_keypair()
    
    payload = b"test payload"
    signature = sign_payload(payload, private_key1)
    
    # Verify with wrong public key
    result = verify_signature(payload, signature, public_key2)
    
    assert result.verified is False


# ─── Input Validation Tests ──────────────────────────────────────────────────

def test_verify_empty_payload():
    """Should reject empty payload."""
    private_key, public_key = generate_test_keypair()
    
    result = verify_signature(b"", bytes(64), public_key)
    
    assert result.verified is False
    assert "SIGNATURE_INVALID" in result.error_code


def test_verify_invalid_signature_length():
    """Should reject signature with wrong length."""
    private_key, public_key = generate_test_keypair()
    payload = b"test payload"
    
    # Signature too short
    result = verify_signature(payload, bytes(32), public_key)
    
    assert result.verified is False
    assert "SIGNATURE_INVALID" in result.error_code


def test_verify_invalid_public_key_length():
    """Should reject public key with wrong length."""
    private_key, public_key = generate_test_keypair()
    payload = b"test payload"
    signature = sign_payload(payload, private_key)
    
    # Public key too short
    result = verify_signature(payload, signature, bytes(16))
    
    assert result.verified is False
    assert result.error_code == "SIGNATURE_INVALID_KEY_LENGTH"


def test_verify_none_public_key():
    """Should reject None public key."""
    result = verify_signature(b"payload", bytes(64), None)
    
    assert result.verified is False
    assert "SIGNATURE_PUBLIC_KEY_MISSING" in result.error_code


def test_verify_none_signature():
    """Should reject None signature."""
    private_key, public_key = generate_test_keypair()
    
    result = verify_signature(b"payload", None, public_key)
    
    assert result.verified is False
    assert result.error_code == "SIGNATURE_MISSING"


# ─── Artifact Signature Verification Tests ───────────────────────────────────

def test_artifact_verification_valid(signed_payload_fixture):
    """Should verify valid artifact signature."""
    result = verify_artifact_signature(
        contents=signed_payload_fixture["payload"],
        metadata_signature=signed_payload_fixture["signature"],
        metadata_public_key=signed_payload_fixture["public_key"],
        payload=signed_payload_fixture["payload"]
    )
    
    assert result.verified is True


def test_artifact_verification_missing_public_key():
    """Should fail when public key is missing."""
    result = verify_artifact_signature(
        contents=b"payload",
        metadata_signature=bytes(64),
        metadata_public_key=None
    )
    
    assert result.verified is False
    assert result.error_code == "SIGNATURE_PUBLIC_KEY_MISSING"


def test_artifact_verification_missing_signature():
    """Should fail when signature is missing."""
    private_key, public_key = generate_test_keypair()
    
    result = verify_artifact_signature(
        contents=b"payload",
        metadata_signature=None,
        metadata_public_key=public_key
    )
    
    assert result.verified is False
    assert result.error_code == "SIGNATURE_MISSING"


# ─── Determinism Tests ───────────────────────────────────────────────────────

def test_verification_deterministic(signed_payload_fixture):
    """Signature verification should be deterministic."""
    result1 = verify_artifact_signature(
        contents=signed_payload_fixture["payload"],
        metadata_signature=signed_payload_fixture["signature"],
        metadata_public_key=signed_payload_fixture["public_key"]
    )
    
    result2 = verify_artifact_signature(
        contents=signed_payload_fixture["payload"],
        metadata_signature=signed_payload_fixture["signature"],
        metadata_public_key=signed_payload_fixture["public_key"]
    )
    
    assert result1.verified == result2.verified
    assert result1.computed_hash == result2.computed_hash


def test_hash_computation():
    """Should compute correct SHA-256 hash."""
    private_key, public_key = generate_test_keypair()
    payload = b"test payload for hashing"
    expected_hash = hashlib.sha256(payload).hexdigest()
    
    signature = sign_payload(payload, private_key)
    result = verify_signature(payload, signature, public_key)
    
    assert result.computed_hash == expected_hash


# ─── Helper Function Tests ───────────────────────────────────────────────────

def test_generate_keypair():
    """Should generate valid keypair."""
    private_key, public_key = generate_test_keypair()
    
    assert len(private_key) == 32
    assert len(public_key) == 32


def test_sign_and_verify_roundtrip():
    """Sign and verify should work together."""
    private_key, public_key = generate_test_keypair()
    
    payload = b"roundtrip test payload"
    signature = sign_payload(payload, private_key)
    
    assert len(signature) == 64
    
    result = verify_signature(payload, signature, public_key)
    assert result.verified is True


def test_result_to_dict():
    """SignatureVerificationResult.to_dict should work correctly."""
    result = SignatureVerificationResult(
        verified=True,
        computed_hash="abc123",
        public_key_hex="def456"
    )
    
    d = result.to_dict()
    
    assert d["verified"] is True
    assert d["computed_hash"] == "abc123"
    assert d["public_key_hex"] == "def456"
    assert d["error_code"] is None
