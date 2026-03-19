import hashlib

from fastapi import APIRouter, HTTPException

from app.logging_config import logger
from app.models.mint_schemas import (
    MintFinalizeRequest,
    MintPrepareRequest,
    MintPrepareResponse,
    NFTMetadata,
    PreparedMetadata,
)
from app.services.ipfs_service import prepare_ipfs_metadata

router = APIRouter()


@router.post("/prepare", response_model=MintPrepareResponse)
async def prepare_mint(request: MintPrepareRequest):
    try:
        logger.info(f"Preparing mint for upload {request.uploadId}")

        if request.metadataUrl:
            ipfs_data = {
                "url": request.metadataUrl,
                "name": request.metadata.get("name", "RIMOS Audit NFT"),
                "symbol": request.metadata.get("symbol", "RIMOS"),
                "provider": "custom",
                "fallbackUsed": False,
            }
        else:
            # Prepare IPFS metadata (real provider first, fallback if needed)
            ipfs_data = prepare_ipfs_metadata(
                request.uploadId,
                request.fileHash,
                request.metadata,
                request.auditData,
            )
        
        # Create a deterministic mock hash based on input (incorporating actual file cryptographic hash)
        hash_input = f"{request.uploadId}{request.walletAddress}{request.fileHash}".encode()
        mint_hash = hashlib.sha256(hash_input).hexdigest()
        
        logger.info(f"Mint prepared successfully: {mint_hash[:16]}...")
        
        return MintPrepareResponse(
            metadata=PreparedMetadata(
                url=ipfs_data["url"],
                provider=ipfs_data.get("provider"),
                fallbackUsed=bool(ipfs_data.get("fallbackUsed", False)),
            ),
            mintHash=mint_hash,
            nftMetadata=NFTMetadata(
                name=ipfs_data["name"],
                symbol=ipfs_data["symbol"]
            )
        )
    except Exception as e:
        logger.error(f"Failed to prepare mint: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to prepare mint: {str(e)}")


@router.post("/finalize")
async def finalize_mint(request: MintFinalizeRequest):
    try:
        # In a real scenario, you'd store the confirmed mint transaction in a database
        logger.info(f"Mint finalized! NFT Address: {request.mintAddress} for Upload: {request.uploadId}")
        
        return {"success": True, "message": "Mint successfully finalized"}
    except Exception as e:
        logger.error(f"Failed to finalize mint: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to finalize mint: {str(e)}")
