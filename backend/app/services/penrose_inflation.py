import hashlib
import math
from typing import Any, Dict, List, Tuple


PHI = (1 + math.sqrt(5)) / 2
INV_PHI = 1 / PHI
PI = math.pi
TWO_PI = 2 * PI


def _sun_seed() -> List[Tuple[int, complex, complex, complex]]:
    """
    Generate star seed: 10 blue triangles = 5 thick rhombi around center.
    Blue triangle: (1, A, B, C) with 108° at A, 36° at B and C.
    For 36° at center (B=0): 10 blue with apex at 0.
    """
    triangles = []
    for i in range(10):
        # B and C on unit circle, 36° apart; center at 0
        angle_b = (2 * i - 1) * PI / 10
        angle_c = (2 * i + 1) * PI / 10
        B = complex(math.cos(angle_b), math.sin(angle_b))
        C = complex(math.cos(angle_c), math.sin(angle_c))
        if i % 2 == 1:
            B, C = C, B
        triangles.append((1, 0j, B, C))
    return triangles


def _sun_seed_field_v6(center: complex = 0j) -> List[Tuple[int, complex, complex, complex]]:
    """
    Penrose Field v6 (client canvas): 10 Robinson *red* triangles (type 0) in the sun.
    Must match reference HTML ``sunSeed`` so isometry alignment scores > 0.
    """
    triangles: List[Tuple[int, complex, complex, complex]] = []
    for i in range(10):
        angle_b = (2 * i - 1) * PI / 10
        angle_c = (2 * i + 1) * PI / 10
        B = complex(math.cos(angle_b), math.sin(angle_b))
        C = complex(math.cos(angle_c), math.sin(angle_c))
        if i % 2 == 1:
            B, C = C, B
        triangles.append((0, center, B, C))
    return triangles


def _subdivide(
    triangles: List[Tuple[int, complex, complex, complex]],
) -> List[Tuple[int, complex, complex, complex]]:
    """Robinson triangle subdivision. Red(0)→1 red+1 blue. Blue(1)→2 blue+1 red."""
    result = []
    for color, A, B, C in triangles:
        if color == 0:
            P = A + (B - A) * INV_PHI
            result.extend([(0, C, P, B), (1, P, C, A)])
        else:
            Q = B + (A - B) * INV_PHI
            R = B + (C - B) * INV_PHI
            result.extend([(1, R, C, A), (1, Q, R, B), (0, R, Q, A)])
    return result


# Integer vertex grid for edge matching (finer than 8-decimal float rounding).
_RHOMBUS_VERTEX_SCALE = 1_000_000_000


def _quantize_pt(z: complex) -> Tuple[int, int]:
    return (
        int(round(z.real * _RHOMBUS_VERTEX_SCALE)),
        int(round(z.imag * _RHOMBUS_VERTEX_SCALE)),
    )


def _from_quant(q: Tuple[int, int]) -> complex:
    return complex(q[0] / _RHOMBUS_VERTEX_SCALE, q[1] / _RHOMBUS_VERTEX_SCALE)


def snap_triangles(
    triangles: List[Tuple[int, complex, complex, complex]],
    decimals: int = 12,
) -> List[Tuple[int, complex, complex, complex]]:
    """Reduce float jitter after subdivide / rotate so shared edges match reliably."""

    def sn(z: complex) -> complex:
        return complex(round(z.real, decimals), round(z.imag, decimals))

    return [(c, sn(A), sn(B), sn(C)) for c, A, B, C in triangles]


def dedupe_robinson_triangles(
    triangles: List[Tuple[int, complex, complex, complex]],
) -> List[Tuple[int, complex, complex, complex]]:
    """
    Remove duplicate triangles (same Robinson color + same three vertices).
    Needed when merging two inflated patches that overlap in the plane.
    """
    seen: set[Tuple[int, Tuple[Tuple[int, int], Tuple[int, int], Tuple[int, int]]]] = set()
    out: List[Tuple[int, complex, complex, complex]] = []
    for col, A, B, C in triangles:
        qs = tuple(sorted({_quantize_pt(A), _quantize_pt(B), _quantize_pt(C)}))
        if len(qs) != 3:
            continue
        key = (col, (qs[0], qs[1], qs[2]))
        if key in seen:
            continue
        seen.add(key)
        out.append((col, A, B, C))
    return out


def _triangles_to_rhombi_v2(
    triangles: List[Tuple[int, complex, complex, complex]],
) -> List[Dict[str, Any]]:
    """
    Build rhombi by matching shared edges between same-colored triangles.
    Fixed-point vertex keys prevent spurious merges that caused overlapping tiles.
    """
    rhombi: List[Dict[str, Any]] = []

    def normalize_edge(a: complex, b: complex) -> Tuple[Tuple[int, int], Tuple[int, int]]:
        pa, pb = _quantize_pt(a), _quantize_pt(b)
        if pa < pb:
            return (pa, pb)
        return (pb, pa)

    edge_to_tris: Dict[Tuple[Tuple[int, int], Tuple[int, int]], List[Tuple[int, int]]] = {}
    for idx, (col, A, B, C) in enumerate(triangles):
        for e in (normalize_edge(A, B), normalize_edge(B, C), normalize_edge(C, A)):
            edge_to_tris.setdefault(e, []).append((idx, col))

    paired: set[int] = set()
    for _edge, tri_list in edge_to_tris.items():
        if len(tri_list) < 2:
            continue
        for i in range(len(tri_list)):
            for j in range(i + 1, len(tri_list)):
                idx_i, col_i = tri_list[i]
                idx_j, col_j = tri_list[j]
                if col_i != col_j or idx_i in paired or idx_j in paired:
                    continue
                ti = triangles[idx_i]
                tj = triangles[idx_j]
                verts_i = [ti[1], ti[2], ti[3]]
                verts_j = [tj[1], tj[2], tj[3]]
                corner_set = {_quantize_pt(v) for v in verts_i + verts_j}
                if len(corner_set) != 4:
                    continue
                pts = [_from_quant(q) for q in corner_set]
                center = sum(pts) / 4.0
                verts = sorted(
                    pts,
                    key=lambda p: math.atan2(p.imag - center.imag, p.real - center.real),
                )
                rhombi.append(
                    {
                        "type": "thick" if col_i == 1 else "thin",
                        "vertices": verts,
                        "center": center,
                    }
                )
                paired.add(idx_i)
                paired.add(idx_j)
                break
            else:
                continue
            break

    return rhombi


def _inflate_penrose_triangles(
    seed_str: str, iterations: int = 6
) -> List[Tuple[int, complex, complex, complex]]:
    """
    Inflate from the legacy blue sun seed with hash rotation; return triangles only.
    Pairing is separate so multiple patches can be merged before _triangles_to_rhombi_v2().
    """
    triangles = _sun_seed()

    h = hashlib.sha256(seed_str.encode()).digest()
    rot = (int.from_bytes(h[:4], "big") % 1000) / 1000.0 * TWO_PI
    for i in range(len(triangles)):
        c, A, B, C = triangles[i]

        def rot_c(z: complex) -> complex:
            return complex(
                z.real * math.cos(rot) - z.imag * math.sin(rot),
                z.real * math.sin(rot) + z.imag * math.cos(rot),
            )

        triangles[i] = (c, rot_c(A), rot_c(B), rot_c(C))

    for _ in range(iterations):
        triangles = _subdivide(triangles)

    return triangles


def _inflate_penrose(seed_str: str, iterations: int = 6) -> List[Dict[str, Any]]:
    """
    Generate Penrose tiling via inflation.
    Seed determines rotation: use hash to rotate initial wheel.
    """
    return _triangles_to_rhombi_v2(_inflate_penrose_triangles(seed_str, iterations))

