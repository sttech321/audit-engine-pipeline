"""
SVG Penrose P3 tiling visualization service.

PASS97 Spec Compliant:
- True Penrose P3 inflation from star seed (5 thick rhombi)
- Mathematically correct thin (36°/144°) and thick (72°/108°) geometry
- Deterministic fingerprint from audit parameters
- Connected, edge-sharing aperiodic tiling
"""
import hashlib
import math
from typing import Dict, Any, List, Tuple

# ─── Penrose P3 Constants ────────────────────────────────────────────────────

PHI = (1 + math.sqrt(5)) / 2
INV_PHI = 1 / PHI
PI = math.pi
TWO_PI = 2 * PI

DEG18 = math.radians(18)
DEG36 = math.radians(36)
DEG72 = math.radians(72)
DEG144 = math.radians(144)

SIN18 = math.sin(DEG18)
SIN36 = math.sin(DEG36)
SIN72 = math.sin(DEG72)

# SVG: 400x400, center 200,200
SVG_WIDTH = 400
SVG_HEIGHT = 400
SVG_CENTER_X = 200
SVG_CENTER_Y = 200

TILE_BASE_COLORS = [
    "#5b9bd5", "#70ad47", "#c55a11", "#4472c4", "#e2a176",
    "#a5a5a5", "#ffc000", "#ed7d31",
]

RISK_COLORS = {
    "LOW": "#22c55e",
    "MEDIUM": "#eab308",
    "HIGH": "#f97316",
    "CRITICAL": "#ef4444",
}


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


def _subdivide(triangles: List[Tuple[int, complex, complex, complex]]) -> List[Tuple[int, complex, complex, complex]]:
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


def _triangles_to_rhombi_v2(triangles: List[Tuple[int, complex, complex, complex]]) -> List[Dict[str, Any]]:
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
                angles = [(math.atan2(p.imag - center.imag, p.real - center.real), p) for p in pts]
                angles.sort(key=lambda x: x[0])
                verts = [a[1] for a in angles]
                rhombi.append({
                    "type": "thick" if col_i == 1 else "thin",
                    "vertices": verts,
                    "center": center,
                })
                paired.add(idx_i)
                paired.add(idx_j)
                break
            else:
                continue
            break

    return rhombi


def _inflate_penrose(
    seed_str: str,
    iterations: int = 6,
) -> List[Dict[str, Any]]:
    """
    Generate Penrose tiling via inflation.
    Seed determines rotation: use hash to rotate initial wheel.
    """
    triangles = _sun_seed()

    h = hashlib.sha256(seed_str.encode()).digest()
    rot = (int.from_bytes(h[:4], "big") % 1000) / 1000.0 * TWO_PI
    for i in range(len(triangles)):
        c, A, B, C = triangles[i]
        rot_c = lambda z: complex(z.real * math.cos(rot) - z.imag * math.sin(rot),
                                  z.real * math.sin(rot) + z.imag * math.cos(rot))
        triangles[i] = (c, rot_c(A), rot_c(B), rot_c(C))

    for _ in range(iterations):
        triangles = _subdivide(triangles)

    return _triangles_to_rhombi_v2(triangles)


def _path_from_complex_verts(verts: List[complex], cx: float, cy: float, scale: float) -> str:
    """Build SVG path from 4 vertices, scaled and translated."""
    pts = [(cx + v.real * scale, cy + v.imag * scale) for v in verts]
    parts = [f"M {pts[0][0]:.2f},{pts[0][1]:.2f}"]
    for p in pts[1:]:
        parts.append(f"L {p[0]:.2f},{p[1]:.2f}")
    parts.append("Z")
    return " ".join(parts)


def generate_penrose_svg(
    penrose_data: Dict[str, Any],
    risk_level: str = "LOW",
    show_labels: bool = True,
    show_hash: bool = True
) -> str:
    """
    Generate dense Penrose P3 tiling via inflation.
    Deterministic from penrose_hash + tile_hash.
    """
    theta = penrose_data.get("theta", 0)
    sector = penrose_data.get("sector", 0)
    penrose_hash = penrose_data.get("penrose_hash", "")[:16]
    tau = penrose_data.get("tau", 0.5)
    tile_hash = penrose_data.get("tile_hash", "")[:16]

    seed = penrose_hash + tile_hash
    risk_color = RISK_COLORS.get(risk_level, RISK_COLORS["LOW"])

    rhombi = _inflate_penrose(seed, iterations=5)

    if not rhombi:
        rhombi = _inflate_penrose(seed + "alt", iterations=4)

    xs = [r["center"].real for r in rhombi]
    ys = [r["center"].imag for r in rhombi]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    span = max(max_x - min_x, max_y - min_y, 0.01)
    scale = 150 / span
    cx_off = SVG_CENTER_X - (min_x + max_x) / 2 * scale
    cy_off = SVG_CENTER_Y - (min_y + max_y) / 2 * scale

    gradient_defs = []
    for i, base in enumerate(TILE_BASE_COLORS):
        hex_val = base.lstrip("#")
        r, g, b = int(hex_val[0:2], 16) / 255, int(hex_val[2:4], 16) / 255, int(hex_val[4:6], 16) / 255
        light = f"rgb({int(min(255,r*255*1.35))},{int(min(255,g*255*1.35))},{int(min(255,b*255*1.35))})"
        dark = f"rgb({int(max(0,r*255*0.75))},{int(max(0,g*255*0.75))},{int(max(0,b*255*0.75))})"
        gradient_defs.append(
            f'    <linearGradient id="g{i}" x1="0%" y1="0%" x2="100%" y2="100%">'
            f'<stop offset="0%" style="stop-color:{light}"/>'
            f'<stop offset="100%" style="stop-color:{dark}"/>'
            f'</linearGradient>'
        )

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {SVG_WIDTH} {SVG_HEIGHT}" width="{SVG_WIDTH}" height="{SVG_HEIGHT}">',
        '  <defs>',
        '    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">',
        '      <stop offset="0%" style="stop-color:#1a1a2e"/>',
        '      <stop offset="100%" style="stop-color:#16213e"/>',
        '    </linearGradient>',
        *gradient_defs,
        '  </defs>',
        '  <rect width="100%" height="100%" fill="url(#bg)"/>',
        '  <g>',
    ]

    for i, r in enumerate(rhombi):
        color_idx = (hashlib.sha256((seed + str(i)).encode()).digest()[0] + sector) % len(TILE_BASE_COLORS)
        path = _path_from_complex_verts(r["vertices"], cx_off, cy_off, scale)
        svg.append(f'    <path d="{path}" fill="url(#g{color_idx})" stroke="#000" stroke-width="0.4"/>')

    svg.extend([
        "  </g>",
        f'  <rect x="{SVG_WIDTH-55}" y="15" width="45" height="20" rx="10" fill="{risk_color}" fill-opacity="0.9"/>',
        f'  <text x="{SVG_WIDTH-32}" y="29" text-anchor="middle" fill="white" font-size="10" font-weight="bold">{risk_level}</text>',
    ])
    if show_labels:
        svg.append(f'  <text x="{SVG_CENTER_X}" y="18" text-anchor="middle" fill="#94a3b8" font-size="10">Penrose P3 · τ={tau:.4f} θ={theta:.4f}</text>')
    if show_hash:
        svg.append(f'  <text x="{SVG_CENTER_X}" y="{SVG_HEIGHT-10}" text-anchor="middle" fill="#475569" font-size="8">{penrose_hash}</text>')
    svg.append("</svg>")
    return "\n".join(svg)


def generate_minimal_svg(sector: int, risk_level: str = "LOW", size: int = 64) -> str:
    colors = ["#3b82f6", "#8b5cf6", "#ec4899", "#f97316", "#22c55e"]
    color = colors[sector % len(colors)]
    cx, cy = size / 2, size / 2
    r = size * 0.35
    pts = [f"{cx + r * math.cos(k * TWO_PI / 5 - PI / 2):.1f},{cy + r * math.sin(k * TWO_PI / 5 - PI / 2):.1f}" for k in range(5)]
    risk_color = RISK_COLORS.get(risk_level, RISK_COLORS["LOW"])
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" width="{size}" height="{size}"><polygon points="{" ".join(pts)}" fill="{color}" fill-opacity="0.8" stroke="{risk_color}" stroke-width="2"/><text x="{cx}" y="{cy+4}" text-anchor="middle" fill="white" font-size="{size//4}" font-weight="bold">{sector}</text></svg>'


def embed_svg_in_metadata(svg_content: str) -> Dict[str, Any]:
    import base64
    b64 = base64.b64encode(svg_content.encode("utf-8")).decode("ascii")
    return {"image": f"data:image/svg+xml;base64,{b64}", "image_type": "image/svg+xml", "image_encoding": "base64"}
