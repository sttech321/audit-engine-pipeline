import re
from typing import Any

from pydantic import BaseModel, field_validator

# Base58 character set (Solana addresses)
BASE58_PATTERN = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")


def validate_base58_address(value: str, field_name: str) -> str:
    """Validate a Base58-encoded Solana address."""
    if not value or not value.strip():
        raise ValueError(f"{field_name} cannot be empty")
    if not BASE58_PATTERN.match(value):
        raise ValueError(f"{field_name} must be a valid Base58 Solana address")
    return value


class MintPrepareRequest(BaseModel):
    uploadId: str
    metadata: dict[str, Any]
    walletAddress: str
    fileHash: str
    auditData: dict[str, Any] | None = None
    metadataUrl: str | None = None

    @field_validator("walletAddress")
    @classmethod
    def validate_wallet(cls, v: str) -> str:
        return validate_base58_address(v, "walletAddress")

    @field_validator("uploadId")
    @classmethod
    def validate_upload_id(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("uploadId cannot be empty")
        return v

    @field_validator("fileHash")
    @classmethod
    def validate_file_hash(cls, v: str) -> str:
        if not v or len(v) != 64:
            raise ValueError("fileHash must be a 64-character SHA-256 hex string")
        if not re.match(r"^[a-fA-F0-9]{64}$", v):
            raise ValueError("fileHash must be a valid hex string")
        return v.lower()


class NFTMetadata(BaseModel):
    name: str
    symbol: str


class PreparedMetadata(BaseModel):
    url: str
    provider: str | None = None
    fallbackUsed: bool = False


class MintPrepareResponse(BaseModel):
    metadata: PreparedMetadata
    mintHash: str
    nftMetadata: NFTMetadata


class IpfsUploadRequest(BaseModel):
    uploadId: str
    fileHash: str
    metadata: dict[str, Any]
    auditData: dict[str, Any] | None = None

    @field_validator("uploadId")
    @classmethod
    def validate_upload_id(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("uploadId cannot be empty")
        return v

    @field_validator("fileHash")
    @classmethod
    def validate_file_hash(cls, v: str) -> str:
        if not v or len(v) != 64:
            raise ValueError("fileHash must be a 64-character SHA-256 hex string")
        if not re.match(r"^[a-fA-F0-9]{64}$", v):
            raise ValueError("fileHash must be a valid hex string")
        return v.lower()


class IpfsUploadResponse(BaseModel):
    url: str
    cid: str
    provider: str | None = None
    fallbackUsed: bool = False


class MintFinalizeRequest(BaseModel):
    mintAddress: str
    uploadId: str
    signature: str

    @field_validator("mintAddress")
    @classmethod
    def validate_mint_address(cls, v: str) -> str:
        return validate_base58_address(v, "mintAddress")

    @field_validator("signature")
    @classmethod
    def validate_signature(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("signature cannot be empty")
        # Solana signatures are Base58-encoded and typically 87-88 characters
        if len(v) < 64:
            raise ValueError("signature appears too short for a valid Solana signature")
        return v

    @field_validator("uploadId")
    @classmethod
    def validate_upload_id(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("uploadId cannot be empty")
        return v
