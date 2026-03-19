from fastapi import APIRouter, HTTPException

from app.logging_config import logger
from app.models.mint_schemas import IpfsUploadRequest, IpfsUploadResponse
from app.services.ipfs_service import prepare_ipfs_metadata

router = APIRouter()


@router.post("/upload", response_model=IpfsUploadResponse)
async def upload_ipfs_metadata(request: IpfsUploadRequest):
    try:
        payload = prepare_ipfs_metadata(
            request.uploadId,
            request.fileHash,
            request.metadata,
            request.auditData,
        )
        return IpfsUploadResponse(
            url=payload["url"],
            cid=payload["cid"],
            provider=payload.get("provider"),
            fallbackUsed=bool(payload.get("fallbackUsed", False)),
        )
    except Exception as exc:
        logger.error(f"IPFS upload endpoint failed: {exc}")
        raise HTTPException(status_code=500, detail=f"IPFS upload failed: {str(exc)}")
