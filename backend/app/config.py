"""
Application configuration with environment variable support.
"""
import os
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )
    
    # API Settings
    app_name: str = "Audit FastAPI Backend"
    app_version: str = "1.0.0"
    debug: bool = False
    
    # CORS Settings
    cors_origins: List[str] = ["http://localhost:3000"]
    cors_allow_credentials: bool = True
    cors_allow_methods: List[str] = ["GET", "POST", "PUT", "DELETE"]
    cors_allow_headers: List[str] = ["*"]
    
    # File Processing Limits
    min_file_size: int = 32  # Minimum bytes for valid audit artifact
    max_file_size: int = 10_000_000_000  # 10GB
    max_batch_files: int = 20  # Maximum files per batch upload
    max_batch_total_size: int = 20_000_000_000  # 20GB total across batch (soft guard)
    
    # Audit Pipeline Constants
    prime_p: int = 2**127 - 1  # Mersenne prime for p-adic arithmetic
    ntt_mod: int = 998_244_353  # NTT-friendly prime (2^23 * 119 + 1)
    ntt_root: int = 3  # Primitive root of NTT_MOD
    
    # Validation Thresholds
    min_byte_diversity: int = 16  # Minimum unique byte values
    min_entropy: float = 2.5  # Minimum Shannon entropy bits/byte
    min_kag_score: float = 0.30  # KAG separability threshold
    
    # Logging
    log_level: str = "INFO"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # ─── Feature Flags (Additive Features) ───────────────────────────────────
    # All new features are opt-out configurable
    
    # File validation features
    validate_file_extension: bool = True  # Enforce .lm3z, .rim0, .rim95 extensions
    validate_mime_type: bool = True  # Validate MIME types
    use_streaming_upload: bool = True  # Use memory-efficient streaming
    
    # Metadata parsing features
    parse_metadata: bool = True  # Parse structured metadata from artifacts
    require_valid_metadata: bool = False  # Fail if metadata parsing fails (False = backward compatible)
    strict_metadata_parsing: bool = True  # Enable strict schema validation (reject extra fields, validate versions)
    
    # Signature verification features
    verify_signatures: bool = True  # Enable Ed25519 signature verification
    require_valid_signature: bool = False  # Fail if signature verification fails (False = backward compatible)
    
    # Abuse protection features
    enable_rate_limiting: bool = True  # Enable per-IP rate limiting
    rate_limit_uploads: str = "10/minute"  # Rate limit for uploads
    enable_deduplication: bool = True  # Enable hash-based deduplication
    enable_replay_detection: bool = True  # Enable replay attack detection
    dedup_ttl_seconds: int = 3600  # TTL for deduplication cache (1 hour)
    replay_window_seconds: int = 300  # Replay detection window (5 minutes)
    
    # Error handling
    use_structured_errors: bool = True  # Use structured error envelope
    hide_internal_errors: bool = True  # Prevent internal error leakage


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance."""
    return Settings()
