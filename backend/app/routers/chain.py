from fastapi import APIRouter

from app.services.artifact_chain import canonical_block_hash, get_artifact_chain, get_chain_seed


router = APIRouter()


@router.get("/chain/blocks")
def get_blocks():
    return {"blocks": get_artifact_chain()}


@router.get("/chain/seed")
def get_seed():
    return {"chain_seed": get_chain_seed()}


@router.get("/chain/verify")
def verify_chain():
    """
    RIM-204: public verifiability endpoint.

    Recompute each block_hash and verify prev_block_hash linkages.
    """
    chain = get_artifact_chain()
    if not chain:
        return {
            "valid": False,
            "block_count": 0,
            "failed_at_index": 0,
            "failure_reason": "empty chain",
            "chain_seed": get_chain_seed(),
        }

    prev_hash = None
    prev_version = None
    for i, block in enumerate(chain):
        recomputed = canonical_block_hash(block)
        if block.get("block_hash") != recomputed:
            return {
                "valid": False,
                "block_count": len(chain),
                "failed_at_index": i,
                "failure_reason": "block_hash mismatch",
                "chain_seed": get_chain_seed(),
            }
        if i == 0:
            prev_hash = block.get("block_hash")
            prev_version = block.get("pipeline_version")
            continue
        if prev_version is not None and block.get("pipeline_version") != prev_version:
            return {
                "valid": False,
                "block_count": len(chain),
                "failed_at_index": i,
                "failure_reason": "pipeline_version mismatch",
                "chain_seed": get_chain_seed(),
            }
        if block.get("prev_block_hash") != prev_hash:
            return {
                "valid": False,
                "block_count": len(chain),
                "failed_at_index": i,
                "failure_reason": "prev_block_hash mismatch",
                "chain_seed": get_chain_seed(),
            }
        prev_hash = block.get("block_hash")
        prev_version = block.get("pipeline_version")

    return {
        "valid": True,
        "block_count": len(chain),
        "failed_at_index": None,
        "failure_reason": None,
        "chain_seed": get_chain_seed(),
    }

