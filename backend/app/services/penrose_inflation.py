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


def _triangles_to_rhombi_v2(
    triangles: List[Tuple[int, complex, complex, complex]],
) -> List[Dict[str, Any]]:
    """
    Build rhombi by matching shared edges. Use vertex-based matching.
    Two triangles form a rhombus if they share an edge and have same color.
    """
    rhombi = []

    def normalize_edge(a: complex, b: complex):
        ar, ar_ = round(a.real, 8), round(a.imag, 8)
        br, br_ = round(b.real, 8), round(b.imag, 8)
        if (ar, ar_) < (br, br_):
            return ((ar, ar_), (br, br_))
        return ((br, br_), (ar, ar_))

    edge_to_tris: Dict[tuple, List[int]] = {}
    for idx, (col, A, B, C) in enumerate(triangles):
        for e in [normalize_edge(A, B), normalize_edge(B, C), normalize_edge(C, A)]:
            edge_to_tris.setdefault(e, []).append((idx, col))

    paired = set()
    for edge, tri_list in edge_to_tris.items():
        if len(tri_list) < 2:
            continue
        for i in range(len(tri_list)):
            for j in range(i + 1, len(tri_list)):
                idx_i, col_i = tri_list[i]
                idx_j, col_j = tri_list[j]
                if col_i != col_j or idx_i in paired or idx_j in paired:
                    continue
                # Same color, shared edge → rhombus
                ti = triangles[idx_i]
                tj = triangles[idx_j]
                verts_i = [ti[1], ti[2], ti[3]]
                verts_j = [tj[1], tj[2], tj[3]]
                all_v = set()
                for v in verts_i + verts_j:
                    all_v.add((round(v.real, 8), round(v.imag, 8)))
                if len(all_v) != 4:
                    continue
                pts = [complex(p[0], p[1]) for p in all_v]
                center = sum(pts) / 4
                angles = [
                    (math.atan2(p.imag - center.imag, p.real - center.real), p)
                    for p in pts
                ]
                angles.sort(key=lambda x: x[0])
                verts = [a[1] for a in angles]
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


def _inflate_penrose(seed_str: str, iterations: int = 6) -> List[Dict[str, Any]]:
    """
    Generate Penrose tiling via inflation.
    Seed determines rotation: use hash to rotate initial wheel.
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

    return _triangles_to_rhombi_v2(triangles)

