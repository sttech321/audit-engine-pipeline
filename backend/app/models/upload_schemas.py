from typing import Any

from pydantic import BaseModel

from app.models.common_schemas import FileInfo, KPI, VerificationStatus


class UploadResponse(BaseModel):
    fileInfo: FileInfo
    kpis: list[KPI]
    verification: VerificationStatus
    fileHash: str
    uploadId: str
    metadata: dict[str, Any]
