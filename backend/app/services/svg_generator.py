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

# Legacy inflation tiling (used by generate_penrose_svg fallback).
# `_inflate_penrose_triangles` is available from penrose_inflation if callers need
# raw tris from the *blue* sun seed; Field v6 viewport uses `_sun_seed_field_v6`
# for background so Robinson colors match the mint patch at boundaries.
from app.services.penrose_inflation import (
    _inflate_penrose,
    _subdivide,
    _sun_seed_field_v6,
    _triangles_to_rhombi_v2,
    dedupe_robinson_triangles,
    snap_triangles,
)

from rim_os_v2 import build_genesis, k5_to_world_position

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

# Subdivision depth for Field v6 viewport: background (origin sun) + mint sun must match
# so Robinson pairing sees a consistent mesh at the patch boundary.
VIEWPORT_SUBDIV_ITERS = 6

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


def _vertex_key(v: complex) -> Tuple[float, float]:
    # Use slightly coarser quantization: inflation vertices accumulate tiny
    # floating error after repeated transforms; 1e-4 still preserves structure
    # but allows robust star-hub detection.
    return (round(v.real, 4), round(v.imag, 4))


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


def _build_canonical_seed(iters: int = 5) -> List[Tuple[int, complex, complex, complex]]:
    """
    Sun at origin (Field v6 / Robinson type-0), subdivided for alignment targets.
    """
    triangles = _sun_seed_field_v6(0j)
    for _ in range(iters):
        triangles = _subdivide(triangles)
    return triangles


def _sun_seed_at(cx: float, cy: float) -> List[Tuple[int, complex, complex, complex]]:
    offset = complex(cx, cy)
    return [
        (color, A + offset, B + offset, C + offset)
        for (color, A, B, C) in _sun_seed_field_v6(0j)
    ]


def _viewport_background_field_tris(iterations: int) -> List[Tuple[int, complex, complex, complex]]:
    """Origin-centred Field v6 sun, subdivided (same Robinson convention as mint)."""
    tris = _sun_seed_field_v6(0j)
    for _ in range(iterations):
        tris = snap_triangles(_subdivide(tris))
    return tris


def _aabb_of_triangles(
    tris: List[Tuple[int, complex, complex, complex]],
) -> Tuple[float, float, float, float]:
    xs: List[float] = []
    ys: List[float] = []
    for _, A, B, C in tris:
        for z in (A, B, C):
            xs.append(z.real)
            ys.append(z.imag)
    if not xs:
        return (0.0, 0.0, 0.0, 0.0)
    return (min(xs), max(xs), min(ys), max(ys))


def _filter_tris_overlapping_aabb(
    tris: List[Tuple[int, complex, complex, complex]],
    x0: float,
    x1: float,
    y0: float,
    y1: float,
    pad: float,
) -> List[Tuple[int, complex, complex, complex]]:
    """Keep triangles whose centroid or any vertex lies in the padded axis-aligned box."""
    xa, xb = x0 - pad, x1 + pad
    ya, yb = y0 - pad, y1 + pad
    out: List[Tuple[int, complex, complex, complex]] = []
    for col, A, B, C in tris:
        inside = False
        for z in (A, B, C):
            if xa <= z.real <= xb and ya <= z.imag <= yb:
                inside = True
                break
        if not inside:
            cx = (A.real + B.real + C.real) / 3.0
            cy = (A.imag + B.imag + C.imag) / 3.0
            if xa <= cx <= xb and ya <= cy <= yb:
                inside = True
        if inside:
            out.append((col, A, B, C))
    return out


def _build_mint_patch(
    k5: List[float],
    canonical_seed_tris: List[Tuple[int, complex, complex, complex]],
    inflate_pre_align: int = 3,
    inflate_after_rotate: int = 3,
) -> Tuple[List[Tuple[int, complex, complex, complex]], float, int]:
    """
    SVG-VIS-008: coherent tiling from a SINGLE global seed.

    Inflate one origin-centered sun scaled large enough to cover the input position,
    subdivide until tiles are fine enough, then crop to a viewport around the input.

    Notes:
    - `canonical_seed_tris` is retained for API compatibility (unused).
    - `inflate_pre_align` / `inflate_after_rotate` are retained; their sum provides a
      baseline subdivision depth, and we add extra iters as scale grows.
    """
    del canonical_seed_tris  # unused in global-seed viewport generation

    wx, wy = k5_to_world_position(k5)
    input_dist = math.hypot(wx, wy)

    # Client invariance rule: keep the Penrose field global and absolute.
    # Using a scale proportional to input_dist normalizes the sampling radius and can
    # make different inputs look artificially similar. Prefer a fixed global scale
    # that covers the expected working region; only grow beyond it if absolutely needed.
    GLOBAL_FIELD_SCALE = 22.0
    scale_factor = max(2.0, GLOBAL_FIELD_SCALE)
    if input_dist > scale_factor * 0.95:
        # Extremely distant inputs: expand enough to include them (best-effort).
        # This trades strict invariance for not returning an empty viewport.
        scale_factor = input_dist * 1.2

    # Start with origin sun, scaled.
    tris = _sun_seed_field_v6(0j)
    tris = [(c, A * scale_factor, B * scale_factor, C * scale_factor) for (c, A, B, C) in tris]

    # Subdivide until tiles are fine enough. Larger scale needs more iters.
    total_iters = int(inflate_pre_align + inflate_after_rotate)
    extra = max(0, int(round(math.log(scale_factor) / math.log(PHI)))) if scale_factor > 1.0 else 0
    total_iters = max(total_iters, total_iters + extra)

    for _ in range(total_iters):
        tris = snap_triangles(_subdivide(tris))

    # Crop to viewport around input position.
    sample = tris[: min(10, len(tris))]
    if sample:
        edges = [abs(B - A) for _, A, B, C in sample]
        avg_edge = sum(edges) / max(1, len(edges))
    else:
        avg_edge = 0.05
    viewport_r = avg_edge * 18.0

    cropped: List[Tuple[int, complex, complex, complex]] = []
    for col, A, B, C in tris:
        cx = (A.real + B.real + C.real) / 3.0
        cy = (A.imag + B.imag + C.imag) / 3.0
        if math.hypot(cx - wx, cy - wy) < viewport_r:
            cropped.append((col, A, B, C))

    # Deterministic orientation: vary with position on the global field.
    # This is an "observer orientation" used by the viewport renderer (θ label + optional rotation),
    # not a change to the underlying global field.
    theta = math.atan2(wy, wx) if (abs(wx) > 1e-12 or abs(wy) > 1e-12) else 0.0
    return cropped, float(theta), len(cropped)


# Alias for callers / docs: mint pipeline returns triangles only, single pairing after merge.
_build_mint_patch_triangles = _build_mint_patch


def _approx_k5_from_tau(tau: List[float], scale: float = 50.0) -> List[float]:
    """Map legacy τ ∈ [0,1]⁵ back to a rough k5 for chain blocks without k5."""
    tt = (list(tau) + [0.5] * 5)[:5]
    return [(float(tt[i]) - 0.5) * 2.0 * scale for i in range(5)]


def _rhombus_path_screen(
    r: Dict[str, Any],
    cx_off: float,
    cy_off: float,
    scale: float,
) -> str:
    verts = r.get("vertices") or []
    if len(verts) != 4:
        return ""
    pts = [(cx_off + v.real * scale, cy_off + v.imag * scale) for v in verts]
    # 2–3 decimals is visually identical at 400×400 but reduces SVG size a lot.
    d = f"M {pts[0][0]:.2f},{pts[0][1]:.2f}"
    for px, py in pts[1:]:
        d += f" L {px:.2f},{py:.2f}"
    return d + " Z"


def _ammann_segments_complex(t: Dict[str, Any]) -> List[Tuple[Tuple[float, float], Tuple[float, float]]]:
    verts = t.get("vertices") or []
    if len(verts) != 4:
        return []
    vs = [(v.real, v.imag) for v in verts]
    m01 = ((vs[0][0] + vs[1][0]) * 0.5, (vs[0][1] + vs[1][1]) * 0.5)
    m12 = ((vs[1][0] + vs[2][0]) * 0.5, (vs[1][1] + vs[2][1]) * 0.5)
    m23 = ((vs[2][0] + vs[3][0]) * 0.5, (vs[2][1] + vs[3][1]) * 0.5)
    m30 = ((vs[3][0] + vs[0][0]) * 0.5, (vs[3][1] + vs[0][1]) * 0.5)
    return [(m01, m23), (m12, m30)]


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
    Viewport: single mint mesh (Field v6 isometry pipeline). Tiles are coloured
    by distance from the patch centroid—round gold core, steel fog when the chain
    visited nearby, dark blue rim—matching the client tile-view mockup.
    """
    del viewport_radius, tau_window_delta  # retained for API compatibility

    risk_color = RISK_COLORS.get(risk_level, RISK_COLORS["LOW"])
    penrose_hash = str(penrose_data.get("penrose_hash", ""))[:16]
    chain_len = len(chain or [])

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
    tau5_norm = [(float(tau_vectors[k]) if k < len(tau_vectors) else 0.5) for k in range(5)]

    k5_in = penrose_data.get("k5")
    if isinstance(k5_in, list) and len(k5_in) >= 5:
        k5: List[float] = [float(k5_in[i]) for i in range(5)]
    else:
        k5 = _approx_k5_from_tau(tau_vectors)

    theme = (
        penrose_data.get("viewport_visual_theme")
        or visual_theme
        or DEFAULT_VIEWPORT_VISUAL_THEME
    )
    if theme not in (VIEWPORT_VISUAL_THEME_REFERENCE, VIEWPORT_VISUAL_THEME_SPEC):
        theme = VIEWPORT_VISUAL_THEME_REFERENCE

    # SVG-VIS-008 / client invariant rule:
    # The Penrose field is global; the input only defines the viewport center.
    # Use world_x/world_y as the viewport center when present (same frame as chunk_positions).
    wx_k5, wy_k5 = k5_to_world_position(k5)
    try:
        wx_in = float(penrose_data.get("world_x", wx_k5))
    except (TypeError, ValueError):
        wx_in = wx_k5
    try:
        wy_in = float(penrose_data.get("world_y", wy_k5))
    except (TypeError, ValueError):
        wy_in = wy_k5
    mint_tris, theta_opt, align_score = _build_mint_patch_triangles(
        k5,
        canonical_seed_tris=[],
        inflate_pre_align=3,
        inflate_after_rotate=VIEWPORT_SUBDIV_ITERS - 3,
    )
    mint_tris = snap_triangles(mint_tris)
    mint_rhombi = _triangles_to_rhombi_v2(mint_tris)

    if not mint_rhombi:
        return generate_penrose_svg(
            penrose_data=penrose_data,
            risk_level=risk_level,
            show_labels=show_labels,
            show_hash=True,
        )

    # Performance: cap rendered rhombi count deterministically so the SVG stays
    # lightweight enough for the web UI to load quickly.
    # Keep the closest tiles to the input anchor (sun-centered framing).
    MAX_RHOMBI = 1000
    if len(mint_rhombi) > MAX_RHOMBI:
        anchor_c = complex(wx_in, wy_in)

        def _k(r: Dict[str, Any]) -> Tuple[float, float, float]:
            c = r.get("center") or anchor_c
            d = abs(c - anchor_c)
            return (d, round(c.real, 6), round(c.imag, 6))

        mint_rhombi = sorted(mint_rhombi, key=_k)[:MAX_RHOMBI]

    visit_xy: List[Tuple[float, float]] = []
    for block in chain or []:
        if block.get("type") == "GENESIS":
            continue
        bk = block.get("k5")
        if isinstance(bk, list) and len(bk) >= 5:
            kb = [float(bk[i]) for i in range(5)]
        else:
            tv = block.get("tau_vectors") or []
            if not tv:
                continue
            tvf = [float(x) for x in tv if isinstance(x, (int, float))]
            if not tvf:
                continue
            kb = _approx_k5_from_tau(tvf)
        visit_xy.append(k5_to_world_position(kb))

    visit_radius = 3.0

    def near_visit(cx: float, cy: float) -> bool:
        return any(math.hypot(cx - px, cy - py) < visit_radius for px, py in visit_xy)

    # Mint-centric framing (matches client canvas “tile view”): a global bbox often
    # shrinks scale to sub-pixel rhombi while the compass stays visible in px space.
    xs: List[float] = []
    ys: List[float] = []
    for r in mint_rhombi:
        for v in r.get("vertices") or []:
            xs.append(v.real)
            ys.append(v.imag)
    if not xs:
        return generate_penrose_svg(
            penrose_data=penrose_data,
            risk_level=risk_level,
            show_labels=show_labels,
            show_hash=True,
        )

    x_lo, x_hi = min(xs), max(xs)
    y_lo, y_hi = min(ys), max(ys)
    span_raw = max(x_hi - x_lo, y_hi - y_lo, 4.0)
    pad = span_raw * 0.20
    span = span_raw + 2 * pad
    vp_cx, vp_cy = wx_in, wy_in
    scale = (SVG_WIDTH * 0.90) / span
    cx_off = SVG_CENTER_X - vp_cx * scale
    cy_off = SVG_CENTER_Y - vp_cy * scale

    # Inner “figure” band: distance from patch centroid — round gold core + blue rim
    # (client canvas); same idea as hub-centered penrose_patch() tiling.
    apex_x, apex_y = vp_cx, vp_cy
    dists_sorted: List[float] = []
    for r in mint_rhombi:
        c = r.get("center")
        if c is None:
            continue
        dists_sorted.append(math.hypot(c.real - apex_x, c.imag - apex_y))
    dists_sorted.sort()
    fig_r = (
        dists_sorted[max(0, min(len(dists_sorted) - 1, int(len(dists_sorted) * 0.30)))]
        if dists_sorted
        else 0.5
    )

    n_mint = len(mint_rhombi)
    n_figure = sum(
        1
        for r in mint_rhombi
        if r.get("center")
        and math.hypot(r["center"].real - apex_x, r["center"].imag - apex_y) < fig_r
    )

    # Use the mint patch's deterministic θ as a viewport rotation so different artifacts
    # don't present with a constant 0° orientation.
    deg = round(math.degrees(theta_opt)) % 360
    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {SVG_WIDTH} {SVG_HEIGHT}" '
        f'width="{SVG_WIDTH}" height="{SVG_HEIGHT}" shape-rendering="geometricPrecision">',
        '  <rect width="100%" height="100%" fill="#0f172a"/>',
        f'  <g id="tiles" transform="rotate({deg} {SVG_CENTER_X} {SVG_CENTER_Y})">',
    ]

    def _rgb(hex_color: str) -> Tuple[int, int, int]:
        h = hex_color.lstrip("#")
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

    def _mix(c1: str, c2: str, a: float) -> str:
        r1, g1, b1 = _rgb(c1)
        r2, g2, b2 = _rgb(c2)
        r = int(r1 * (1 - a) + r2 * a)
        g = int(g1 * (1 - a) + g2 * a)
        b = int(b1 * (1 - a) + b2 * a)
        return f"#{r:02x}{g:02x}{b:02x}"

    def _shade_rh(rh: Dict[str, Any], base: str) -> str:
        verts = rh.get("vertices") or []
        if len(verts) != 4:
            return base
        a0, a1 = verts[0], verts[1]
        ang = math.atan2(a1.imag - a0.imag, a1.real - a0.real)
        k = (math.cos(ang - math.radians(35)) + 1.0) * 0.5
        al = 0.07 + 0.06 * k
        cen = rh.get("center") or sum(verts) / 4
        al += 0.03 * math.sin(cen.real * 1.618 + cen.imag * 1.414)
        al = min(0.18, max(0.03, al))
        return _mix(base, "#ffffff", al)

    def _emit_rh(
        rh: Dict[str, Any],
        base: str,
        stroke: str,
        stro_op: float,
        stro_w: float,
        bar_op: float,
        bar_w: float,
    ) -> None:
        fill = _shade_rh(rh, base)
        path = _rhombus_path_screen(rh, cx_off, cy_off, scale)
        svg.append(
            f'    <path d="{path}" fill="{fill}" stroke="{stroke}" '
            f'stroke-opacity="{stro_op:.2f}" stroke-width="{stro_w:.2f}" '
            f'stroke-linejoin="round" stroke-linecap="round"/>'
        )
        if bar_op <= 0.0 or bar_w <= 0.0:
            return
        for (a, b) in _ammann_segments_complex(rh):
            x1, y1 = cx_off + a[0] * scale, cy_off + a[1] * scale
            x2, y2 = cx_off + b[0] * scale, cy_off + b[1] * scale
            svg.append(
                f'    <line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" '
                f'stroke="#facc15" stroke-opacity="{bar_op:.2f}" stroke-width="{bar_w:.2f}" '
                f'stroke-linecap="round"/>'
            )

    # SVG-VIS-007: pipeline-driven coloring from chunk_positions when present.
    raw_cp = penrose_data.get("chunk_positions")
    if not isinstance(raw_cp, list):
        raw_cp = penrose_data.get("chunkPositions")

    chunk_pos: List[Dict[str, Any]] = []
    if isinstance(raw_cp, list):
        for cp in raw_cp:
            if not isinstance(cp, dict):
                continue
            try:
                chunk_pos.append(
                    {
                        "wx": float(cp.get("wx", 0.0)),
                        "wy": float(cp.get("wy", 0.0)),
                        "sep": float(cp.get("sep", 0.0)),
                        "ent": float(cp.get("ent", 0.0)),
                        "ano": bool(cp.get("ano", False)),
                    }
                )
            except (TypeError, ValueError):
                continue

    viz_mode = "pipeline" if chunk_pos else "legacy"

    # Map chunks to nearest rhombus center (rotate chunks to patch frame if needed).
    cos_t, sin_t = math.cos(theta_opt), math.sin(theta_opt)
    tile_chunks: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    if chunk_pos:
        centers_nn: List[Tuple[int, float, float]] = []
        for ri, r in enumerate(mint_rhombi):
            cen = r.get("center")
            if cen is not None:
                centers_nn.append((ri, cen.real, cen.imag))
        for cp in chunk_pos:
            wx, wy = cp["wx"], cp["wy"]
            rx = wx * cos_t - wy * sin_t
            ry = wx * sin_t + wy * cos_t
            best_ri = -1
            best_d2 = float("inf")
            for ri, cx, cy in centers_nn:
                d2 = (rx - cx) ** 2 + (ry - cy) ** 2
                if d2 < best_d2:
                    best_d2 = d2
                    best_ri = ri
            if best_ri >= 0:
                tile_chunks[best_ri].append(cp)

    figure_count = (
        sum(1 for ri in range(n_mint) if tile_chunks.get(ri))
        if chunk_pos
        else n_figure
    )

    def _tile_color(ri: int, rh: Dict[str, Any]) -> Tuple[str, str, float, float, float, float]:
        """Return (base, stroke, stroke_op, stroke_w, bar_op, bar_w) from pipeline or legacy fallbacks."""
        mapped = tile_chunks.get(ri, [])
        thick = rh["type"] == "thick"

        if not chunk_pos:
            c = rh.get("center")
            if c and math.hypot(c.real - apex_x, c.imag - apex_y) < fig_r:
                base = "#f59e0b" if thick else "#fcd34d"
                return base, "#7c2d12", 0.55, 0.75, 0.70, 0.55
            base = "#24364f" if thick else "#1f2f46"
            return base, "#1e293b", 0.32, 0.35, 0.0, 0.0

        if not mapped:
            base = "#1a2332" if thick else "#161e2d"
            return base, "#1e293b", 0.20, 0.30, 0.0, 0.0

        n_map = len(mapped)
        avg_sep = sum(c["sep"] for c in mapped) / n_map
        has_anomaly = any(c["ano"] for c in mapped)
        density = min(
            1.0,
            (n_map / max(1, len(chunk_pos))) * len(mint_rhombi) * 0.5,
        )

        if has_anomaly:
            base = "#ef4444" if thick else "#f87171"
            # Show bars only on anomalies (keeps SVG light but highlights critical tiles).
            return base, "#7f1d1d", 0.70, 0.85, 0.55, 0.45

        t_sep = min(1.0, max(0.0, avg_sep))
        if thick:
            gold = (245, 158, 11)
            teal = (20, 184, 166)
        else:
            gold = (252, 211, 77)
            teal = (94, 234, 212)
        rr = int(gold[0] * t_sep + teal[0] * (1.0 - t_sep))
        gg = int(gold[1] * t_sep + teal[1] * (1.0 - t_sep))
        bb = int(gold[2] * t_sep + teal[2] * (1.0 - t_sep))
        base = f"#{rr:02x}{gg:02x}{bb:02x}"
        # Keep Ammann bars off by default for performance; enable only in very dense regions.
        bar_op = 0.35 * density if density > 0.75 else 0.0
        return base, "#7c2d12", 0.42 + 0.18 * density, 0.60, bar_op, 0.40

    for ri, r in enumerate(mint_rhombi):
        b, st, so, sw, bo, bw = _tile_color(ri, r)
        _emit_rh(r, b, st, so, sw, bo, bw)

    gm = build_genesis()["genesis_mints"]
    g_info = [
        {"label": "c", "tau": gm[0]["tau_pentagrid"], "col": "#6366f1"},
        {"label": "h", "tau": gm[1]["tau_pentagrid"], "col": "#8b5cf6"},
        {"label": "G", "tau": gm[2]["tau_pentagrid"], "col": "#a78bfa"},
    ]
    for g in g_info:
        dtau = [float(g["tau"][k]) - tau5_norm[k] for k in range(5)]
        dx = sum(dtau[k] * math.cos(2 * math.pi * k / 5) for k in range(5))
        dy = sum(dtau[k] * math.sin(2 * math.pi * k / 5) for k in range(5))
        dist = math.hypot(dx, dy)
        if dist < 1e-9:
            continue
        ux, uy = dx / dist, dy / dist
        mx, my = SVG_CENTER_X, SVG_CENTER_Y
        rim = SVG_WIDTH * 0.36
        x2, y2 = mx + ux * rim, my + uy * rim
        svg.append(
            f'    <line x1="{mx:.1f}" y1="{my:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="{g["col"]}" stroke-width="0.8" stroke-dasharray="3 3" opacity="0.6"/>'
        )
        ax = x2 - ux * 8 + uy * 4
        ay = y2 - uy * 8 - ux * 4
        bx = x2 - ux * 8 - uy * 4
        by = y2 - uy * 8 + ux * 4
        svg.append(
            f'    <polygon points="{x2:.1f},{y2:.1f} {ax:.1f},{ay:.1f} {bx:.1f},{by:.1f}" '
            f'fill="{g["col"]}" opacity="0.7"/>'
        )
        svg.append(
            f'    <text x="{mx + ux * (rim + 14):.1f}" y="{my + uy * (rim + 14):.1f}" '
            f'text-anchor="middle" fill="{g["col"]}" font-size="9" font-weight="bold">'
            f'{g["label"]}</text>'
        )

    if chunk_pos:
        ly = SVG_HEIGHT - 68
        svg.append(
            f'  <rect x="8" y="{ly}" width="130" height="28" rx="4" '
            f'fill="#0f172a" fill-opacity="0.85" stroke="#334155" stroke-width="0.5"/>'
        )
        for i, (col, label) in enumerate(
            [
                ("#f59e0b", "high KAG"),
                ("#14b8a6", "low KAG"),
                ("#ef4444", "anom."),
            ]
        ):
            x = 14 + i * 40
            svg.append(
                f'  <rect x="{x:.0f}" y="{ly + 6:.0f}" width="8" height="8" rx="1" fill="{col}"/>'
            )
            svg.append(
                f'  <text x="{x + 11:.0f}" y="{ly + 14:.0f}" fill="#94a3b8" font-size="6">{label}</text>'
            )

    svg.extend(
        [
            "  </g>",
            f'  <rect x="{SVG_WIDTH-55}" y="15" width="45" height="20" rx="10" '
            f'fill="{risk_color}" fill-opacity="0.9"/>',
            f'  <text x="{SVG_WIDTH-32}" y="29" text-anchor="middle" fill="white" '
            f'font-size="10" font-weight="bold">{risk_level}</text>',
        ]
    )
    if show_labels:
        tau_str = ",".join(f"{v:.3f}" for v in tau_vectors[:3])
        svg.extend(
            [
                f'  <text x="{SVG_CENTER_X}" y="16" text-anchor="middle" fill="#94a3b8" '
                f'font-size="9">Field v6 · chain={chain_len} · tiles={n_mint} · '
                f'figure={figure_count} · θ={deg}° · align={align_score} · {theme} · {viz_mode}</text>',
                f'  <text x="{SVG_CENTER_X}" y="{SVG_HEIGHT-10}" text-anchor="middle" '
                f'fill="#475569" font-size="8">τ=[{tau_str}...] · {penrose_hash}</text>',
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
