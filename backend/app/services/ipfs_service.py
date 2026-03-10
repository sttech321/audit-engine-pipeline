import hashlib

def prepare_ipfs_metadata(upload_id: str, file_hash: str, user_metadata: dict) -> dict:
    """
    Simulates the decentralized storage pinning process, tying the input deterministically to the output hash.
    """
    
    # Create a mock IPFS URL that incorporates both the upload sequence ID and the specific file hash.
    unique_identifier = f"QmMockHash{upload_id[:8]}{file_hash[:8]}"
    mock_ipfs_url = f"https://gateway.pinata.cloud/ipfs/{unique_identifier}"
    
    return {
        "url": mock_ipfs_url,
        "name": user_metadata.get("name", "Pass97 Audit NFT"),
        "symbol": "PASS97",
        "description": user_metadata.get("description", f"Cryptographic audit artifact {file_hash}"),
        "attributes": user_metadata.get("attributes", [])
    }
