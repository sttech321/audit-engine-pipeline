"""
Backward-compatible schema exports.

Prefer importing from:
- app.models.common_schemas
- app.models.upload_schemas
- app.models.mint_schemas
"""

from app.models.common_schemas import FileInfo, KPI, VerificationStatus
from app.models.mint_schemas import (
    MintFinalizeRequest,
    MintPrepareRequest,
    MintPrepareResponse,
    NFTMetadata,
    PreparedMetadata,
)
from app.models.upload_schemas import UploadResponse

__all__ = [
    "FileInfo",
    "KPI",
    "VerificationStatus",
    "UploadResponse",
    "MintPrepareRequest",
    "NFTMetadata",
    "PreparedMetadata",
    "MintPrepareResponse",
    "MintFinalizeRequest",
]
