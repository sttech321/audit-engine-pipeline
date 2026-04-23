from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, HTTPException, Query

from app.services.artifact_chain import get_artifact_chain


router = APIRouter()


def _non_genesis_blocks(chain: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [b for b in chain if b.get("type") != "GENESIS" and int(b.get("index", 0)) > 0]


def _parse_barycentric(s: str) -> Tuple[float, float, float]:
    parts = [p.strip() for p in (s or "").split(",")]
    if len(parts) != 3:
        raise ValueError("barycentric must be 'a,b,c'")
    return (float(parts[0]), float(parts[1]), float(parts[2]))


def _dist(a: Tuple[float, float, float], b: Tuple[float, float, float]) -> float:
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2) ** 0.5


@router.get("/register/commits")
def list_commits():
    chain = get_artifact_chain()
    blocks = _non_genesis_blocks(chain)
    out = []
    for b in blocks:
        out.append(
            {
                "index": b.get("index"),
                "artifact_hash": b.get("artifact_hash"),
                "block_hash": b.get("block_hash"),
                "barycentric": b.get("barycentric"),
            }
        )
    return {"commits": out}


@router.get("/register/neighbors")
def neighbors(
    barycentric: Optional[str] = Query(None, description="comma-separated 'a,b,c'"),
    artifact_hash: Optional[str] = Query(None, description="artifact hash to look up barycentric"),
    max_distance: float = Query(0.15, ge=0.0),
    limit: int = Query(50, ge=1, le=500),
):
    chain = get_artifact_chain()
    blocks = _non_genesis_blocks(chain)
    if not blocks:
        return {"neighbors": []}

    if artifact_hash:
        base_block = next((b for b in blocks if str(b.get("artifact_hash")) == artifact_hash), None)
        if not base_block:
            raise HTTPException(status_code=404, detail="artifact_hash not found")
        bc = base_block.get("barycentric") or [0.0, 0.0, 0.0]
        base = (float(bc[0]), float(bc[1]), float(bc[2]))
    elif barycentric:
        try:
            base = _parse_barycentric(barycentric)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
    else:
        raise HTTPException(status_code=422, detail="provide barycentric or artifact_hash")

    scored = []
    for b in blocks:
        bc = b.get("barycentric") or [0.0, 0.0, 0.0]
        other = (float(bc[0]), float(bc[1]), float(bc[2]))
        d = _dist(base, other)
        if d <= max_distance:
            scored.append((d, b))

    scored.sort(key=lambda x: x[0])
    out = []
    for d, b in scored[:limit]:
        out.append(
            {
                "distance": d,
                "index": b.get("index"),
                "artifact_hash": b.get("artifact_hash"),
                "block_hash": b.get("block_hash"),
                "barycentric": b.get("barycentric"),
            }
        )
    return {"neighbors": out}

