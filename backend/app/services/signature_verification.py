"""
Ed25519 signature verification service.

STRICT IMPLEMENTATION:
- No fallback logic
- Single verification path (over raw payload)
- Fails fast with clear error messages

Ed25519 internally hashes the message, so we verify the raw payload directly.
"""
import hashlib
from typing import Optional, Tuple

from app.logging_config import logger


# ─── Signature Verification Result ───────────────────────────────────────────

class SignatureVerificationResult:
    """Result of Ed25519 signature verification."""
    
    def __init__(
        self,
        verified: bool,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
        computed_hash: Optional[str] = None,
        public_key_hex: Optional[str] = None
    ):
        self.verified = verified
        self.error_code = error_code
        self.error_message = error_message
        self.computed_hash = computed_hash
        self.public_key_hex = public_key_hex
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "verified": self.verified,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "computed_hash": self.computed_hash,
            "public_key_hex": self.public_key_hex
        }


def verify_signature(
    payload: bytes,
    signature: bytes,
    public_key: bytes
) -> SignatureVerificationResult:
    """
    Verify Ed25519 signature using pynacl.
    
    STRICT: Single verification path, no fallbacks.
    Ed25519 signatures are verified over the raw payload.
    Ed25519 internally uses SHA-512 during signing/verification.
    
    Args:
        payload: The signed content (raw bytes)
        signature: Ed25519 signature (64 bytes)
        public_key: Ed25519 public key (32 bytes)
        
    Returns:
        SignatureVerificationResult with verification status and details
    """
    # Validate inputs - strict checks
    if payload is None:
        return SignatureVerificationResult(
            verified=False,
            error_code="SIGNATURE_INVALID_INPUT",
            error_message="Payload cannot be None"
        )
    
    if len(payload) == 0:
        return SignatureVerificationResult(
            verified=False,
            error_code="SIGNATURE_INVALID_INPUT",
            error_message="Empty payload"
        )
    
    if signature is None:
        return SignatureVerificationResult(
            verified=False,
            error_code="SIGNATURE_MISSING",
            error_message="Signature is None"
        )
    
    if len(signature) != 64:
        return SignatureVerificationResult(
            verified=False,
            error_code="SIGNATURE_INVALID_LENGTH",
            error_message=f"Invalid signature length: expected 64, got {len(signature)}"
        )
    
    if public_key is None:
        return SignatureVerificationResult(
            verified=False,
            error_code="SIGNATURE_PUBLIC_KEY_MISSING",
            error_message="Public key is None"
        )
    
    if len(public_key) != 32:
        return SignatureVerificationResult(
            verified=False,
            error_code="SIGNATURE_INVALID_KEY_LENGTH",
            error_message=f"Invalid public key length: expected 32, got {len(public_key)}"
        )
    
    # Compute SHA-256 hash of payload (for logging/debugging, not verification)
    computed_hash = hashlib.sha256(payload).hexdigest()
    public_key_hex = public_key.hex()
    
    try:
        from nacl.signing import VerifyKey
        from nacl.exceptions import BadSignatureError
        
        # Create verify key from public key bytes
        verify_key = VerifyKey(public_key)
        
        # Verify the signature over the raw payload
        # Ed25519 internally hashes with SHA-512, so we don't pre-hash
        verify_key.verify(payload, signature)
        
        return SignatureVerificationResult(
            verified=True,
            computed_hash=computed_hash,
            public_key_hex=public_key_hex
        )
        
    except BadSignatureError:
        return SignatureVerificationResult(
            verified=False,
            error_code="SIGNATURE_VERIFICATION_FAILED",
            error_message="Signature verification failed: signature does not match payload",
            computed_hash=computed_hash,
            public_key_hex=public_key_hex
        )
    except ImportError:
        logger.error("pynacl not installed - signature verification unavailable")
        return SignatureVerificationResult(
            verified=False,
            error_code="SIGNATURE_DEPENDENCY_MISSING",
            error_message="Signature verification unavailable: pynacl not installed"
        )
    except ValueError as e:
        # Invalid key format
        return SignatureVerificationResult(
            verified=False,
            error_code="SIGNATURE_INVALID_KEY",
            error_message=f"Invalid public key format: {str(e)}",
            computed_hash=computed_hash,
            public_key_hex=public_key_hex
        )
    except Exception as e:
        logger.error(f"Signature verification error: {e}")
        return SignatureVerificationResult(
            verified=False,
            error_code="SIGNATURE_ERROR",
            error_message=f"Signature verification error: {str(e)}",
            computed_hash=computed_hash,
            public_key_hex=public_key_hex
        )


def verify_artifact_signature(
    contents: bytes,
    metadata_signature: Optional[bytes],
    metadata_public_key: Optional[bytes],
    payload: Optional[bytes] = None
) -> SignatureVerificationResult:
    """
    Verify signature of an audit artifact using extracted metadata.
    
    STRICT: Requires both signature and public key. No fallbacks.
    
    Args:
        contents: Full file contents (NOT used - payload MUST be provided)
        metadata_signature: Signature from parsed metadata (required)
        metadata_public_key: Public key from parsed metadata (required)
        payload: Extracted payload (required)
        
    Returns:
        SignatureVerificationResult with verification status
    """
    # STRICT: Public key is required
    if metadata_public_key is None:
        return SignatureVerificationResult(
            verified=False,
            error_code="SIGNATURE_PUBLIC_KEY_MISSING",
            error_message="No public key present in artifact metadata"
        )
    
    # STRICT: Signature is required
    if metadata_signature is None:
        return SignatureVerificationResult(
            verified=False,
            error_code="SIGNATURE_MISSING",
            error_message="No signature present in artifact metadata"
        )
    
    # STRICT: Payload must be explicitly provided
    if payload is None:
        return SignatureVerificationResult(
            verified=False,
            error_code="SIGNATURE_INVALID_INPUT",
            error_message="Payload must be explicitly provided for verification"
        )
    
    return verify_signature(
        payload=payload,
        signature=metadata_signature,
        public_key=metadata_public_key
    )


def generate_test_keypair() -> Tuple[bytes, bytes]:
    """
    Generate a test Ed25519 keypair.
    
    This is for testing purposes only.
    
    Returns:
        Tuple of (private_key_bytes, public_key_bytes)
    """
    try:
        from nacl.signing import SigningKey
        
        signing_key = SigningKey.generate()
        return bytes(signing_key), bytes(signing_key.verify_key)
    except ImportError:
        raise RuntimeError("pynacl not installed")


def sign_payload(payload: bytes, private_key: bytes) -> bytes:
    """
    Sign a payload using Ed25519.
    
    This is for testing purposes only.
    
    Args:
        payload: Data to sign
        private_key: Ed25519 private key (32 bytes)
        
    Returns:
        Signature bytes (64 bytes)
    """
    try:
        from nacl.signing import SigningKey
        
        signing_key = SigningKey(private_key)
        signed = signing_key.sign(payload)
        return signed.signature
    except ImportError:
        raise RuntimeError("pynacl not installed")
