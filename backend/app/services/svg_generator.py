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

# Legacy inflation tiling (used by generate_penrose_svg fallback)
from app.services.penrose_inflation import _inflate_penrose

# SVG-VIS-004+005 v3 viewport: pentagrid absolute coords
from rim_os_v2 import penrose_patch_raw, genesis_combined_tau, build_genesis

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

    # ======================================================================
    # NEW VIEWPORT PIPELINE (SVG-VIS-004+005) — strict τ geometry
    #
    # Legacy viewport system exists above in history but is fully bypassed:
    # - NO inflation tiling
    # - NO τ projections / masks
    # - NO adjacency / scoring logic
    # ======================================================================

    def _estimate_tile_size_from_tiles(tiles0: List[Dict[str, Any]]) -> float:
        # Median edge length across a sample of tiles; robust enough for tolerance + scale.
        edges: List[float] = []
        for t in tiles0[:500]:
            vs = t.get("v") or []
            if len(vs) != 4:
                continue
            for a, b in zip(vs, vs[1:] + vs[:1]):
                edges.append(math.hypot(a[0] - b[0], a[1] - b[1]))
        edges.sort()
        return edges[len(edges) // 2] if edges else 1.0

    def _tile_path_raw(t: Dict[str, Any], cx_off0: float, cy_off0: float, scale0: float) -> Optional[str]:
        # Enforce a valid rhombus: exactly 4 unique vertices, cyclic order.
        vs = t.get("v") or []
        if len(vs) != 4:
            return None
        uniq = {(round(v[0], 10), round(v[1], 10)) for v in vs}
        if len(uniq) != 4:
            return None
        cx0 = float(t["cx"])
        cy0 = float(t["cy"])
        vs0 = list(uniq)
        vs0.sort(key=lambda p: math.atan2(p[1] - cy0, p[0] - cx0))
        pts = [(cx_off0 + v[0] * scale0, cy_off0 + v[1] * scale0) for v in vs0]
        d = f"M {pts[0][0]:.2f},{pts[0][1]:.2f}"
        for px, py in pts[1:]:
            d += f" L {px:.2f},{py:.2f}"
        return d + " Z"

    # ── GLOBAL MAP M (build once) ───────────────────────────────────────────
    global_tiles = getattr(generate_penrose_svg_viewport, "_p3_global_tiles_v1", None)
    if global_tiles is None:
        tau_genesis = genesis_combined_tau()
        global_tiles = penrose_patch_raw(tau_genesis, N=7)
        setattr(generate_penrose_svg_viewport, "_p3_global_tiles_v1", global_tiles)

    if not global_tiles:
        return generate_penrose_svg(
            penrose_data=penrose_data,
            risk_level=risk_level,
            show_labels=show_labels,
            show_hash=True,
        )
    # Debug: global field size
    try:
        print(f"tiles: {len(global_tiles)}")
    except Exception:
        pass

    # ── GLOBAL SCALE/TRANSLATE (no τ-as-position) ───────────────────────────
    # We render the fixed global field, scaled to the canvas. τ only selects
    # ACTIVE tiles; it does not move the camera.
    global_edge = _estimate_tile_size_from_tiles(global_tiles)
    target_px = 34.0  # 25–50px target range
    scale = max(8.0, min(200.0, target_px / max(global_edge, 1e-9)))

    xs = [float(t["cx"]) for t in global_tiles]
    ys = [float(t["cy"]) for t in global_tiles]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    cx0 = (min_x + max_x) * 0.5
    cy0 = (min_y + max_y) * 0.5
    cx_off = SVG_CENTER_X - cx0 * scale
    cy_off = SVG_CENTER_Y - cy0 * scale

    # Cull to viewport for performance, still based only on the global field bbox.
    half = (SVG_WIDTH / (2 * scale)) * 1.10
    visible = [
        t
        for t in global_tiles
        if abs(float(t["cx"]) - cx0) <= half and abs(float(t["cy"]) - cy0) <= half
    ]
    # Debug: visible viewport size
    try:
        print(f"visible_tiles: {len(visible)}")
    except Exception:
        pass

    # ── τ FILTER (CRITICAL) ────────────────────────────────────────────────
    # Keep τ in the unit torus [0,1) per spec.
    tau5 = [((float(tau_vectors[i]) if i < len(tau_vectors) else 0.5) % 1.0) for i in range(5)]

    def _wrap_dist_01(a: float, b: float) -> float:
        diff = abs(a - b)
        return diff if diff <= 0.5 else (1.0 - diff)

    def is_active_tile(tile: Dict[str, Any], tau: List[float]) -> bool:
        score = 0
        cx = float(tile["cx"])
        cy = float(tile["cy"])
        for k in range(5):
            angle = 2 * math.pi * k / 5
            ex = math.cos(angle)
            ey = math.sin(angle)
            proj = cx * ex + cy * ey
            frac = proj % 1.0
            diff = abs(frac - float(tau[k]))
            if diff > 0.5:
                diff = 1.0 - diff
            if diff < 0.102:  # tuned threshold
                score += 1
        return score >= 3  # strict but stable

    # ── Remove isolated active tiles (no adjacency/BFS expansion) ───────────
    # Keep only active tiles that have >=3 active neighbours within radius.
    radius = max(global_edge, 1e-9) * 1.10
    r2 = radius * radius

    def has_neighbor(tile: Dict[str, Any], tiles: List[Dict[str, Any]]) -> bool:
        count = 0
        cx = float(tile["cx"])
        cy = float(tile["cy"])
        for t in tiles:
            if t is tile:
                continue
            dx = cx - float(t["cx"])
            dy = cy - float(t["cy"])
            if dx * dx + dy * dy < r2:
                count += 1
                if count >= 3:
                    return True
        return False

    # Compute active on the global field (τ is a filter over M).
    # IMPORTANT: neighbors are evaluated only within the rendered viewport.
    ACTIVE = [t for t in visible if is_active_tile(t, tau5)]
    final_active = [t for t in ACTIVE if has_neighbor(t, ACTIVE)]

    # ── DEBUG CHECK (MANDATORY) ─────────────────────────────────────────────
    try:
        total = len(visible) or 1
        active_pct = (len(final_active) / total) * 100.0
        print(f"Active tiles: {active_pct:.2f}%")
    except Exception:
        pass

    # ── SVG layers (base → fog → figure) ────────────────────────────────────
    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {SVG_WIDTH} {SVG_HEIGHT}" width="{SVG_WIDTH}" height="{SVG_HEIGHT}">',
        ' <rect width="100%" height="100%" fill="#0f172a"/>',
        ' <g id="tiles">',
    ]

    # Base (dark navy)
    for t in visible:
        fill = "#1e3a5f" if t["type"] == "thick" else "#172a4a"
        d = _tile_path_raw(t, cx_off, cy_off, scale)
        if d is None:
            continue
        svg.append(
            f'  <path d="{d}" fill="{fill}" stroke="#0b223b" stroke-opacity="0.22" stroke-width="0.6"/>'
        )

    # Active tiles (gold islands via τ filter, isolated removed)
    final_active_keys: set[Tuple[int, int]] = set()
    qk = max(global_edge * 0.15, 1e-9)
    for t in final_active:
        final_active_keys.add((int(round(float(t["cx"]) / qk)), int(round(float(t["cy"]) / qk))))

    n_active = 0
    for t in visible:
        if (int(round(float(t["cx"]) / qk)), int(round(float(t["cy"]) / qk))) not in final_active_keys:
            continue
        fill = "#f59e0b" if t["type"] == "thick" else "#fcd34d"
        d = _tile_path_raw(t, cx_off, cy_off, scale)
        if d is None:
            continue
        svg.append(
            f'  <path d="{d}" fill="{fill}" stroke="#d97706" stroke-opacity="0.85" stroke-width="0.8"/>'
        )
        n_active += 1

    # ── Genesis compass (τ difference, no τ→XY projection) ──────────────────
    # Map direction using the first two τ components as an explicit direction
    # vector in screen space (no pentagrid basis projection).
    gm = build_genesis()["genesis_mints"]
    g_info = [
        {"label": "c", "tau": gm[0]["tau_pentagrid"], "col": "#6366f1"},
        {"label": "ℏ", "tau": gm[1]["tau_pentagrid"], "col": "#8b5cf6"},
        {"label": "G", "tau": gm[2]["tau_pentagrid"], "col": "#a78bfa"},
    ]
    for g in g_info:
        dt0 = float(g["tau"][0]) - float(tau_vectors[0] if len(tau_vectors) > 0 else 0.5)
        dt1 = float(g["tau"][1]) - float(tau_vectors[1] if len(tau_vectors) > 1 else 0.5)
        dist = math.hypot(dt0, dt1)
        if dist < 1e-12:
            continue
        ux, uy = dt0 / dist, dt1 / dist
        mx, my = SVG_CENTER_X, SVG_CENTER_Y
        rim = SVG_WIDTH * 0.36
        x2, y2 = mx + ux * rim, my + uy * rim
        svg.append(f' <line x1="{mx:.1f}" y1="{my:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{g["col"]}" stroke-width="0.8" stroke-dasharray="3 3" opacity="0.6"/>')
        ax = x2 - ux * 8 + uy * 4
        ay = y2 - uy * 8 - ux * 4
        bx = x2 - ux * 8 - uy * 4
        by = y2 - uy * 8 + ux * 4
        svg.append(f' <polygon points="{x2:.1f},{y2:.1f} {ax:.1f},{ay:.1f} {bx:.1f},{by:.1f}" fill="{g["col"]}" opacity="0.7"/>')
        svg.append(f' <text x="{mx + ux * (rim + 14):.1f}" y="{my + uy * (rim + 14):.1f}" text-anchor="middle" fill="{g["col"]}" font-size="9" font-weight="bold">{g["label"]}</text>')

    # ── Risk badge + labels ───────────────────────────────────────────────────
    svg.extend(
        [
            " </g>",
            f' <rect x="{SVG_WIDTH-55}" y="15" width="45" height="20" rx="10" fill="{risk_color}" fill-opacity="0.9"/>',
            f' <text x="{SVG_WIDTH-32}" y="29" text-anchor="middle" fill="white" font-size="10" font-weight="bold">{risk_level}</text>',
        ]
    )
    if show_labels:
        tau_str = ",".join(f"{v:.3f}" for v in tau_vectors[:3])
        svg.extend(
            [
                f' <text x="{SVG_CENTER_X}" y="16" text-anchor="middle" fill="#94a3b8" font-size="9">Global M · Chain={chain_len} · N=7 · {n_active} active tiles</text>',
                f' <text x="{SVG_CENTER_X}" y="{SVG_HEIGHT-10}" text-anchor="middle" fill="#475569" font-size="8">τ=[{tau_str}...] · {penrose_hash}</text>',
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
