"""
SVG Penrose P3 tiling visualization service.

RIMOS Spec Compliant:
- True Penrose P3 inflation from star seed (5 thick rhombi)
- Mathematically correct thin (36°/144°) and thick (72°/108°) geometry
- Deterministic fingerprint from audit parameters
- Connected, edge-sharing aperiodic tiling
"""
import hashlib
import json
import math
from collections import defaultdict
from typing import Dict, Any, List, Optional, Tuple

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

# SVG-VIS-003: mint anchor in tiling bbox (avoids inflation star zone)
MINT_BBOX_MARGIN = 0.15
# τ-window for rhombus signature (cut-and-project match to audit τ)
MINT_TAU_WINDOW_DELTA = 0.12
# Viewport fraction of tiling span (SVG-VIS-003 §7: 0.35–0.40 for density without star-artifact zone)
DEFAULT_VIEWPORT_RADIUS = 0.38
# Fraction of view_span used as half-extent of the visible window (higher → more tiles, more star formations)
VIEWPORT_HALF_SPAN_FACTOR = 0.68

# "reference" = light field + star-hub colors (client mockup). "spec" = SVG-VIS-003 dimmed manifold + gold τ.
VIEWPORT_VISUAL_THEME_REFERENCE = "reference"
VIEWPORT_VISUAL_THEME_SPEC = "spec"
DEFAULT_VIEWPORT_VISUAL_THEME = VIEWPORT_VISUAL_THEME_REFERENCE

def _genesis_tau_vector(anchor_key: str) -> List[float]:
    """Deterministic 5D τ for Genesis anchors (c, ℏ, G) — stable across runs."""
    d = hashlib.sha256(f"RIMOS_GENESIS|{anchor_key}".encode()).digest()
    return [((d[i] + d[(i + 5) % 32]) % 256) / 255.0 for i in range(5)]


_GENESIS_CLUSTER: List[Tuple[str, str]] = [
    ("c", "c"),
    ("ℏ", "hbar"),
    ("G", "G"),
]


def _frac01(x: float) -> float:
    v = x - math.floor(x)
    return v if v >= 0.0 else v + 1.0


def _tau5_pad(tau: List[float]) -> List[float]:
    out = [float(tau[i]) for i in range(min(5, len(tau)))]
    while len(out) < 5:
        out.append(0.5)
    return out


def _circular_dist_torus(a: float, b: float) -> float:
    fa, fb = _frac01(a), _frac01(b)
    diff = abs(fa - fb)
    if diff > 0.5:
        diff = 1.0 - diff
    return diff


def _p5_from_center(cx: float, cy: float) -> List[float]:
    """de Bruijn / cut-and-project 5D fractional coords for rhombus center (SVG-VIS-003)."""
    p5: List[float] = []
    for k in range(5):
        v = cx * math.cos(2 * PI * k / 5) + cy * math.sin(2 * PI * k / 5)
        p5.append(_frac01(v))
    return p5


def _rhombus_in_tau_signature(p5: List[float], tau: List[float], delta: float) -> bool:
    tau5 = _tau5_pad(tau)
    for k in range(5):
        if _circular_dist_torus(p5[k], tau5[k]) > delta:
            return False
    return True


def _vertex_key(v: complex) -> Tuple[float, float]:
    return (round(v.real, 5), round(v.imag, 5))


def _penrose_star_hub_centers(rhombi: List[Dict[str, Any]]) -> List[Tuple[float, float]]:
    """Vertices where five thick rhombi meet (local five-fold star hubs on P3)."""
    vert_rhombi: Dict[Tuple[float, float], List[int]] = defaultdict(list)
    for ri, r in enumerate(rhombi):
        for v in r["vertices"]:
            vert_rhombi[_vertex_key(v)].append(ri)
    hubs: List[Tuple[float, float]] = []
    for key, r_indices in vert_rhombi.items():
        if len(r_indices) != 5:
            continue
        uniq = set(r_indices)
        if len(uniq) != 5:
            continue
        if all(rhombi[i]["type"] == "thick" for i in uniq):
            hubs.append((key[0], key[1]))
    return hubs


def _star_hub_tile_fills(rhombi: List[Dict[str, Any]], global_seed: str) -> Dict[int, str]:
    """Thick rhombi in a 5-thick star: magenta vs pale gold (deterministic per hub)."""
    magenta = "#d946ef"
    pale_gold = "#fcd34d"
    fills: Dict[int, str] = {}
    for hx, hy in _penrose_star_hub_centers(rhombi):
        key = (round(hx, 5), round(hy, 5))
        indices: List[int] = []
        for ri, r in enumerate(rhombi):
            if r["type"] != "thick":
                continue
            for v in r["vertices"]:
                if _vertex_key(v) == key:
                    indices.append(ri)
                    break
        if len(indices) != 5:
            continue
        hbyte = hashlib.sha256(f"{global_seed}|{hx:.5f}|{hy:.5f}".encode()).digest()[0]
        color = magenta if (hbyte % 2 == 0) else pale_gold
        for ri in indices:
            fills.setdefault(ri, color)
    return fills


def _mint_anchor_from_tau_bbox(
    tau_vectors: List[float],
    min_x: float,
    max_x: float,
    min_y: float,
    max_y: float,
) -> Tuple[float, float]:
    """
    Map τ[0], τ[1] into tiling bbox with margin (avoids inflation star zone).
    No modulo on derived artifact coordinates — only τ inputs drive interpolation.
    """
    t0 = float(tau_vectors[0]) if len(tau_vectors) > 0 else 0.5
    t1 = float(tau_vectors[1]) if len(tau_vectors) > 1 else 0.5
    t0 = min(1.0, max(0.0, t0))
    t1 = min(1.0, max(0.0, t1))
    m = MINT_BBOX_MARGIN
    span_x = max_x - min_x
    span_y = max_y - min_y
    x = min_x + (m + t0 * (1.0 - 2.0 * m)) * span_x
    y = min_y + (m + t1 * (1.0 - 2.0 * m)) * span_y
    return (x, y)


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


def _chain_seed(chain: List[Dict[str, Any]]) -> str:
    """
    Derive a deterministic seed from chain state.

    The global map must shift when chain history shifts, so we include stable
    per-block values in canonical JSON form.
    """
    normalized_blocks = []
    for block in sorted(chain or [], key=lambda b: b.get("index", 0)):
        tau_values = block.get("tau_vectors", [])
        if not isinstance(tau_values, list):
            tau_values = [tau_values]

        normalized_tau: List[float] = []
        for value in tau_values:
            try:
                normalized_tau.append(float(value))
            except (TypeError, ValueError):
                continue

        anchors = block.get("anchors", [])
        if not isinstance(anchors, list):
            anchors = [str(anchors)]

        normalized_blocks.append(
            {
                "index": int(block.get("index", 0)),
                "block_hash": str(block.get("block_hash", "")),
                "tau_vectors": normalized_tau,
                "anchors": [str(anchor) for anchor in anchors],
            }
        )

    payload = json.dumps(
        normalized_blocks,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def generate_penrose_svg_viewport(
    penrose_data: Dict[str, Any],
    chain: List[Dict[str, Any]],
    risk_level: str = "LOW",
    viewport_radius: float = DEFAULT_VIEWPORT_RADIUS,
    show_labels: bool = True,
    tau_window_delta: Optional[float] = None,
    visual_theme: str = DEFAULT_VIEWPORT_VISUAL_THEME,
) -> str:
    """
    Render a viewport on the single global Penrose P3 tiling M (chain seed).

    Underlying geometry is Penrose P3–type rhombi from inflation (true P3 / de Bruijn dual).
    visual_theme "reference": light paper field, star hubs (magenta/pale gold), τ signature gold — client mockup.
    visual_theme "spec": SVG-VIS-003 dimmed manifold + gold τ + Genesis (§4.4).
    """
    global_seed = _chain_seed(chain)
    risk_color = RISK_COLORS.get(risk_level, RISK_COLORS["LOW"])
    sector = int(penrose_data.get("sector", 0))
    penrose_hash = str(penrose_data.get("penrose_hash", ""))[:16]
    chain_len = len(chain or [])
    delta = (
        MINT_TAU_WINDOW_DELTA
        if tau_window_delta is None
        else min(max(tau_window_delta, 1e-6), 0.49)
    )

    tau_raw = penrose_data.get("tau_vectors", penrose_data.get("tau", [0.5]))
    if not isinstance(tau_raw, list):
        tau_raw = [tau_raw]

    tau_vectors: List[float] = []
    for value in tau_raw:
        try:
            tau_vectors.append(float(value))
        except (TypeError, ValueError):
            continue
    if not tau_vectors:
        tau_vectors = [0.5]

    theme = (
        penrose_data.get("viewport_visual_theme")
        or visual_theme
        or DEFAULT_VIEWPORT_VISUAL_THEME
    )
    if theme not in (VIEWPORT_VISUAL_THEME_REFERENCE, VIEWPORT_VISUAL_THEME_SPEC):
        theme = VIEWPORT_VISUAL_THEME_REFERENCE

    # One global tiling from chain — shared manifold M (does not vary per mint).
    rhombi: List[Dict[str, Any]] = _inflate_penrose(global_seed, iterations=6)
    if not rhombi:
        rhombi = _inflate_penrose(global_seed + "|fallback", iterations=5)
    if not rhombi:
        return generate_penrose_svg(
            penrose_data=penrose_data,
            risk_level=risk_level,
            show_labels=show_labels,
            show_hash=True,
        )

    for r in rhombi:
        cx = r["center"].real
        cy = r["center"].imag
        r["p5"] = _p5_from_center(cx, cy)

    xs = [r["center"].real for r in rhombi]
    ys = [r["center"].imag for r in rhombi]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    span = max(max_x - min_x, max_y - min_y, 0.01)

    artifact_x, artifact_y = _mint_anchor_from_tau_bbox(
        tau_vectors, min_x, max_x, min_y, max_y
    )
    display_x, display_y = artifact_x, artifact_y

    normalized_radius = min(max(viewport_radius, 0.2), 1.0)
    view_span = span * normalized_radius
    half_span = view_span * VIEWPORT_HALF_SPAN_FACTOR

    visible_indices = [
        i
        for i, r in enumerate(rhombi)
        if abs(r["center"].real - display_x) < half_span
        and abs(r["center"].imag - display_y) < half_span
    ]
    if len(visible_indices) < 20:
        view_span = min(span * 1.6, view_span * 2.2)
        half_span = view_span * VIEWPORT_HALF_SPAN_FACTOR
        visible_indices = [
            i
            for i, r in enumerate(rhombi)
            if abs(r["center"].real - display_x) < half_span
            and abs(r["center"].imag - display_y) < half_span
        ]

    scale = (SVG_WIDTH * 0.88) / max(view_span, 0.01)
    cx_off = SVG_CENTER_X - display_x * scale
    cy_off = SVG_CENTER_Y - display_y * scale

    gold_fill = "#fbbf24"

    gradient_defs = []
    for gi, base in enumerate(TILE_BASE_COLORS):
        hex_val = base.lstrip("#")
        red = int(hex_val[0:2], 16) / 255
        green = int(hex_val[2:4], 16) / 255
        blue = int(hex_val[4:6], 16) / 255
        light = f"rgb({int(min(255, red * 255 * 1.35))},{int(min(255, green * 255 * 1.35))},{int(min(255, blue * 255 * 1.35))})"
        dark = f"rgb({int(max(0, red * 255 * 0.75))},{int(max(0, green * 255 * 0.75))},{int(max(0, blue * 255 * 0.75))})"
        gradient_defs.append(
            f'    <linearGradient id="gv{gi}" x1="0%" y1="0%" x2="100%" y2="100%">'
            f'<stop offset="0%" style="stop-color:{light}"/>'
            f'<stop offset="100%" style="stop-color:{dark}"/>'
            f"</linearGradient>"
        )

    if theme == VIEWPORT_VISUAL_THEME_REFERENCE:
        bg_stops = (
            '      <stop offset="0%" style="stop-color:#ebe3d4"/>',
            '      <stop offset="100%" style="stop-color:#e0d4bc"/>',
        )
        defs_inner = ["  <defs>", '    <linearGradient id="bgv" x1="0%" y1="0%" x2="100%" y2="100%">', *bg_stops, "    </linearGradient>", "  </defs>"]
    else:
        bg_stops = (
            '      <stop offset="0%" style="stop-color:#0f172a"/>',
            '      <stop offset="100%" style="stop-color:#1e293b"/>',
        )
        defs_inner = [
            "  <defs>",
            '    <linearGradient id="bgv" x1="0%" y1="0%" x2="100%" y2="100%">',
            *bg_stops,
            "    </linearGradient>",
            *gradient_defs,
            "  </defs>",
        ]

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {SVG_WIDTH} {SVG_HEIGHT}" width="{SVG_WIDTH}" height="{SVG_HEIGHT}">',
        *defs_inner,
        '  <rect width="100%" height="100%" fill="url(#bgv)"/>',
        '  <g id="tiles">',
    ]

    star_fills: Dict[int, str] = {}
    if theme == VIEWPORT_VISUAL_THEME_REFERENCE:
        star_fills = _star_hub_tile_fills(rhombi, global_seed)

    base_fill_ref = "#c9b89a"
    base_stroke_ref = "#4a3f36"

    # Non–τ-signature tiles
    for ri in visible_indices:
        rhombus = rhombi[ri]
        p5 = rhombus.get("p5")
        if p5 is None:
            p5 = _p5_from_center(rhombus["center"].real, rhombus["center"].imag)
        if _rhombus_in_tau_signature(p5, tau_vectors, delta):
            continue
        path = _path_from_complex_verts(rhombus["vertices"], cx_off, cy_off, scale)
        if theme == VIEWPORT_VISUAL_THEME_REFERENCE:
            fill = star_fills.get(ri, base_fill_ref)
            svg.append(
                f'    <path d="{path}" fill="{fill}" stroke="{base_stroke_ref}" '
                f'stroke-width="0.5" fill-opacity="0.94"/>'
            )
        else:
            color_idx = (
                hashlib.sha256((global_seed + str(ri)).encode()).digest()[0] + sector
            ) % len(TILE_BASE_COLORS)
            svg.append(
                f'    <path d="{path}" fill="url(#gv{color_idx})" stroke="#334155" '
                f'stroke-width="0.4" fill-opacity="0.18"/>'
            )

    # τ signature (gold + risk stroke)
    for ri in visible_indices:
        rhombus = rhombi[ri]
        p5 = rhombus.get("p5")
        if p5 is None:
            p5 = _p5_from_center(rhombus["center"].real, rhombus["center"].imag)
        if not _rhombus_in_tau_signature(p5, tau_vectors, delta):
            continue
        path = _path_from_complex_verts(rhombus["vertices"], cx_off, cy_off, scale)
        sw = "1.05" if theme == VIEWPORT_VISUAL_THEME_REFERENCE else "1.2"
        fo = "0.82" if theme == VIEWPORT_VISUAL_THEME_REFERENCE else "0.82"
        svg.append(
            f'    <path d="{path}" fill="{gold_fill}" stroke="{risk_color}" '
            f'stroke-width="{sw}" fill-opacity="{fo}"/>'
        )

    marker_x = SVG_CENTER_X
    marker_y = SVG_CENTER_Y
    marker_r = 5 if theme == VIEWPORT_VISUAL_THEME_REFERENCE else 8

    # Genesis cluster: faint markers in-view or direction ticks at rim
    rim = min(SVG_WIDTH, SVG_HEIGHT) * 0.42
    for label, gkey in _GENESIS_CLUSTER:
        gt = _genesis_tau_vector(gkey)
        gx, gy = _mint_anchor_from_tau_bbox(gt, min_x, max_x, min_y, max_y)
        in_win = (
            abs(gx - display_x) < half_span * 1.02
            and abs(gy - display_y) < half_span * 1.02
        )
        sx = cx_off + gx * scale
        sy = cy_off + gy * scale
        if in_win and 0 <= sx <= SVG_WIDTH and 0 <= sy <= SVG_HEIGHT:
            if theme == VIEWPORT_VISUAL_THEME_REFERENCE:
                svg.append(
                    f'    <circle cx="{sx:.1f}" cy="{sy:.1f}" r="3.5" fill="#a8a29e" '
                    f'stroke="#57534e" stroke-width="0.65" fill-opacity="0.55"/>'
                )
                svg.append(
                    f'    <text x="{sx:.1f}" y="{sy + 1.2:.1f}" text-anchor="middle" '
                    f'fill="#44403c" font-size="7" font-weight="600">{label}</text>'
                )
            else:
                svg.append(
                    f'    <circle cx="{sx:.1f}" cy="{sy:.1f}" r="3.5" fill="#e2e8f0" '
                    f'stroke="#64748b" stroke-width="0.6" fill-opacity="0.35"/>'
                )
                svg.append(
                    f'    <text x="{sx:.1f}" y="{sy + 1.2:.1f}" text-anchor="middle" '
                    f'fill="#94a3b8" font-size="7" font-weight="600">{label}</text>'
                )
        else:
            dx = gx - display_x
            dy = gy - display_y
            dist = math.hypot(dx, dy)
            if dist < 1e-9:
                continue
            ux, uy = dx / dist, dy / dist
            x2 = marker_x + ux * rim
            y2 = marker_y + uy * rim
            gc = "#57534e" if theme == VIEWPORT_VISUAL_THEME_REFERENCE else "#475569"
            svg.append(
                f'    <line x1="{marker_x:.1f}" y1="{marker_y:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                f'stroke="{gc}" stroke-width="0.5" stroke-dasharray="2 2" opacity="0.55"/>'
            )
            tx = marker_x + ux * (rim + 12)
            ty = marker_y + uy * (rim + 12)
            tc = "#44403c" if theme == VIEWPORT_VISUAL_THEME_REFERENCE else "#64748b"
            svg.append(
                f'    <text x="{tx:.1f}" y="{ty:.1f}" text-anchor="middle" fill="{tc}" '
                f'font-size="7" opacity="0.85">{label}</text>'
            )

    cross = 10 if theme == VIEWPORT_VISUAL_THEME_REFERENCE else 14
    m_opacity = "0.55" if theme == VIEWPORT_VISUAL_THEME_REFERENCE else "0.4"
    fill_op = "0.75" if theme == VIEWPORT_VISUAL_THEME_REFERENCE else "0.9"
    svg.extend(
        [
            "  </g>",
            f'  <circle cx="{marker_x}" cy="{marker_y}" r="{marker_r + 4}" fill="none" stroke="{risk_color}" stroke-width="1.5" opacity="{m_opacity}"/>',
            f'  <circle cx="{marker_x}" cy="{marker_y}" r="{marker_r}" fill="{risk_color}" fill-opacity="{fill_op}" stroke="white" stroke-width="1"/>',
            f'  <line x1="{marker_x - cross}" y1="{marker_y}" x2="{marker_x + cross}" y2="{marker_y}" stroke="{risk_color}" stroke-width="0.8" opacity="0.6"/>',
            f'  <line x1="{marker_x}" y1="{marker_y - cross}" x2="{marker_x}" y2="{marker_y + cross}" stroke="{risk_color}" stroke-width="0.8" opacity="0.6"/>',
            f'  <rect x="{SVG_WIDTH - 55}" y="15" width="45" height="20" rx="10" fill="{risk_color}" fill-opacity="0.9"/>',
            f'  <text x="{SVG_WIDTH - 32}" y="29" text-anchor="middle" fill="white" font-size="10" font-weight="bold">{risk_level}</text>',
        ]
    )

    if show_labels:
        tau_preview = ",".join(f"{value:.3f}" for value in tau_vectors[:3])
        tau_label = f"τ=[{tau_preview}{'...' if len(tau_vectors) > 3 else ''}]"
        c1 = "#57534e" if theme == VIEWPORT_VISUAL_THEME_REFERENCE else "#94a3b8"
        c2 = "#44403c" if theme == VIEWPORT_VISUAL_THEME_REFERENCE else "#475569"
        svg.extend(
            [
                f'  <text x="{SVG_CENTER_X}" y="16" text-anchor="middle" fill="{c1}" font-size="9">Global M · Chain={chain_len} blocks · δ={delta:.2f}</text>',
                f'  <text x="{SVG_CENTER_X}" y="{SVG_HEIGHT - 10}" text-anchor="middle" fill="{c2}" font-size="8">{tau_label} · {penrose_hash}</text>',
            ]
        )

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
