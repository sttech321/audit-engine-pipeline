import hashlib
from typing import Any

import httpx

from app.config import get_settings

def _fallback_cid(upload_id: str, file_hash: str) -> str:
    seed = hashlib.sha256(f"{upload_id}:{file_hash}".encode("utf-8")).hexdigest()
    return f"QmMock{seed[:40]}"


def _normalize_attributes(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    normalized: list[dict[str, Any]] = []
    for item in raw:
        if isinstance(item, dict) and "trait_type" in item and "value" in item:
            normalized.append({"trait_type": item["trait_type"], "value": item["value"]})
    return normalized


def _build_metadata_payload(
    upload_id: str,
    file_hash: str,
    user_metadata: dict[str, Any],
    audit_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    audit = audit_data or {}
    integrity_score = audit.get("integrityScore", "N/A")
    risk_level = audit.get("riskLevel", "Unknown")
    verification_status = audit.get("verificationStatus", "Unknown")
    report_reference = audit.get("reportReference", f"/report/{upload_id}")

    attributes = _normalize_attributes(user_metadata.get("attributes"))
    required_attributes = [
        {"trait_type": "Integrity Score", "value": integrity_score},
        {"trait_type": "Risk Level", "value": risk_level},
        {"trait_type": "Artifact Hash", "value": file_hash},
        {"trait_type": "Verification Status", "value": verification_status},
        {"trait_type": "Report Reference", "value": report_reference},
    ]

    return {
        "name": user_metadata.get("name", f"RIMOS Audit Certificate #{upload_id[:8]}"),
        "symbol": user_metadata.get("symbol", "RIMOS"),
        "description": user_metadata.get(
            "description",
            f"Deterministic audit certificate for artifact {file_hash[:16]}...",
        ),
        "external_url": report_reference,
        "attributes": required_attributes + attributes,
    }


def _upload_pinata(payload: dict[str, Any]) -> tuple[str, str] | None:
    settings = get_settings()
    jwt = settings.pinata_jwt.strip()
    api_key = settings.pinata_api_key.strip()
    api_secret = settings.pinata_api_secret.strip()
    if not jwt and not (api_key and api_secret):
        return None

    headers = {"Content-Type": "application/json"}
    if jwt:
        headers["Authorization"] = f"Bearer {jwt}"
    else:
        headers["pinata_api_key"] = api_key
        headers["pinata_secret_api_key"] = api_secret

    with httpx.Client(timeout=20.0) as client:
        response = client.post(
            "https://api.pinata.cloud/pinning/pinJSONToIPFS",
            json={"pinataContent": payload},
            headers=headers,
        )
        response.raise_for_status()
        cid = response.json().get("IpfsHash")
        if not cid:
            return None
        return cid, f"https://gateway.pinata.cloud/ipfs/{cid}"


def _upload_nft_storage(payload: dict[str, Any]) -> tuple[str, str] | None:
    settings = get_settings()
    token = settings.nft_storage_token.strip()
    if not token:
        return None

    with httpx.Client(timeout=20.0) as client:
        response = client.post(
            "https://api.nft.storage/upload",
            json=payload,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
        response.raise_for_status()
        body = response.json()
        cid = body.get("value", {}).get("cid")
        if not cid:
            return None
        return cid, f"https://nftstorage.link/ipfs/{cid}"


def prepare_ipfs_metadata(
    upload_id: str,
    file_hash: str,
    user_metadata: dict[str, Any],
    audit_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Try uploading metadata to IPFS providers, then fall back to a deterministic mock URL.
    This layer is intentionally non-blocking for the core audit/report flow.
    """
    payload = _build_metadata_payload(upload_id, file_hash, user_metadata, audit_data)

    settings = get_settings()
    provider = settings.ipfs_provider.strip().lower()
    upload_order = (
        ["pinata", "nft_storage"]
        if provider in {"", "auto"}
        else [provider]
    )

    for candidate in upload_order:
        try:
            if candidate == "pinata":
                result = _upload_pinata(payload)
            elif candidate in {"nft.storage", "nft_storage", "nftstorage"}:
                result = _upload_nft_storage(payload)
            else:
                result = None
            if result:
                cid, url = result
                return {
                    "cid": cid,
                    "url": url,
                    "name": payload["name"],
                    "symbol": payload["symbol"],
                    "description": payload["description"],
                    "attributes": payload["attributes"],
                    "provider": candidate,
                    "fallbackUsed": False,
                }
        except Exception:
            continue

    cid = _fallback_cid(upload_id, file_hash)
    return {
        "cid": cid,
        "url": f"https://gateway.pinata.cloud/ipfs/{cid}",
        "name": payload["name"],
        "symbol": payload["symbol"],
        "description": payload["description"],
        "attributes": payload["attributes"],
        "provider": "fallback",
        "fallbackUsed": True,
    }
