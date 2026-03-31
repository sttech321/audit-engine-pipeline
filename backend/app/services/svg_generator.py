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

    # ── Resolution grows with chain length ──────────────────────────────────
    N = 6 + min(3, int(math.log10(max(1, chain_len))))

    # ── Global Penrose P3 field (inflation patch, cached) ───────────────────
    # Revert to the last “closer” implementation: full-canvas aperiodic field.
    field_cache = getattr(generate_penrose_svg_viewport, "_p3_cache_v9", None)
    if field_cache is None:
        raw_field = _inflate_penrose("RIMOS_P3_GLOBAL_FIELD_V2", iterations=10)
        if not raw_field:
            return generate_penrose_svg(
                penrose_data=penrose_data,
                risk_level=risk_level,
                show_labels=show_labels,
                show_hash=True,
            )

        edge_lens: List[float] = []
        for r in raw_field[:1200]:
            vs = r.get("vertices") or []
            if len(vs) == 4:
                edge_lens.append(abs(vs[1] - vs[0]))
        edge_lens.sort()
        med = edge_lens[len(edge_lens) // 2] if edge_lens else 1.0
        factor = 1.0 / max(med, 1e-9)

        tmp: List[Dict[str, Any]] = []
        for r in raw_field:
            vs = r.get("vertices") or []
            if len(vs) != 4:
                continue
            scaled_vs = [v * factor for v in vs]
            center = r.get("center", sum(vs) / 4) * factor
            cx, cy = center.real, center.imag
            scaled_vs.sort(key=lambda v: math.atan2(v.imag - cy, v.real - cx))
            tmp.append({"type": r.get("type", "thick"), "vertices": scaled_vs, "center": center})

        rot = math.radians(23.0)
        cr = math.cos(rot)
        sr = math.sin(rot)

        def _rot(z: complex) -> complex:
            return complex(z.real * cr - z.imag * sr, z.real * sr + z.imag * cr)

        centers = [r["center"] for r in tmp]
        xs = [c.real for c in centers]
        ys = [c.imag for c in centers]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)

        cand_xy = [
            (0.25, 0.25),
            (0.25, 0.50),
            (0.25, 0.75),
            (0.50, 0.25),
            (0.50, 0.50),
            (0.50, 0.75),
            (0.75, 0.25),
            (0.75, 0.50),
            (0.75, 0.75),
        ]
        candidates: List[complex] = []
        for qx, qy in cand_xy:
            tx = min_x * (1 - qx) + max_x * qx
            ty = min_y * (1 - qy) + max_y * qy
            candidates.append(
                min(tmp, key=lambda r: (r["center"].real - tx) ** 2 + (r["center"].imag - ty) ** 2)["center"]
            )

        def _build_field(anchor: complex) -> List[Dict[str, Any]]:
            out: List[Dict[str, Any]] = []
            for r in tmp:
                out.append(
                    {
                        "type": r["type"],
                        "vertices": [_rot(v - anchor) for v in r["vertices"]],
                        "center": _rot(r["center"] - anchor),
                    }
                )
            return out

        best_field: Optional[List[Dict[str, Any]]] = None
        best_score = -1.0
        for a in candidates:
            cand_field = _build_field(a)
            hubs = _penrose_star_hub_centers(cand_field)
            clear = min(math.hypot(hx, hy) for hx, hy in hubs) if hubs else 999.0
            score = clear - 0.02 * abs(_rot(a))
            if score > best_score:
                best_score = score
                best_field = cand_field

        field_cache = best_field or _build_field(candidates[0])

        # NOTE: Do NOT perform a second “hub-free re-anchor” here.
        # That step can move the origin close to the finite field boundary,
        # producing mostly-empty viewports. We rely on the initial anchor
        # selection above to keep the origin away from hubs without drifting
        # to the edge.
        setattr(generate_penrose_svg_viewport, "_p3_cache_v9", field_cache)

    rhombi: List[Dict[str, Any]] = field_cache

    # ── Tile size calibration (25–50px target) ──────────────────────────────
    edge_lens2: List[float] = []
    for r in rhombi[:800]:
        vs = r["vertices"]
        if len(vs) == 4:
            edge_lens2.append(abs(vs[1] - vs[0]))
    edge_lens2.sort()
    med_edge = edge_lens2[len(edge_lens2) // 2] if edge_lens2 else 1.0
    target_px = 34.0
    scale = max(10.0, min(120.0, target_px / max(med_edge, 1e-6)))
    half = (SVG_WIDTH / (2 * scale)) * 1.10

    tau5_norm = [(float(tau_vectors[k]) if k < len(tau_vectors) else 0.5) % 1.0 for k in range(5)]

    def _tau_to_xy(tau5: List[float]) -> Tuple[float, float]:
        dx = 0.0
        dy = 0.0
        for k in range(5):
            v = float(tau5[k] if k < len(tau5) else 0.5) - 0.5
            dx += v * math.cos(2 * math.pi * k / 5)
            dy += v * math.sin(2 * math.pi * k / 5)
        return (dx, dy)

    dx, dy = _tau_to_xy(tau5_norm)
    gain = half * 0.90
    vp_x = min(max(dx * gain, -half * 0.32), half * 0.32)
    vp_y = min(max(dy * gain, -half * 0.32), half * 0.32)

    visible = [r for r in rhombi if abs(r["center"].real) <= half and abs(r["center"].imag) <= half]
    cx_off = SVG_CENTER_X
    cy_off = SVG_CENTER_Y

    dirs = [(math.cos(2 * math.pi * k / 5), math.sin(2 * math.pi * k / 5)) for k in range(5)]
    phase = [2 * math.pi * tau5_norm[k] for k in range(5)]

    def _mask_val(x: float, y: float) -> float:
        s = 0.0
        for k in range(5):
            s += math.cos((x * dirs[k][0] + y * dirs[k][1]) / max(med_edge, 1e-6) * 0.9 + phase[k])
        return s / 5.0

    vscale = 200_000
    edge_to_ids: Dict[Tuple[Tuple[int, int], Tuple[int, int]], List[int]] = {}
    for i, r in enumerate(visible):
        vs = [(int(round(v.real * vscale)), int(round(v.imag * vscale))) for v in r["vertices"]]
        ccx = sum(p[0] for p in vs) / 4.0
        ccy = sum(p[1] for p in vs) / 4.0
        vs.sort(key=lambda p: math.atan2(p[1] - ccy, p[0] - ccx))
        for a, b in zip(vs, vs[1:] + vs[:1]):
            e = (a, b) if a < b else (b, a)
            edge_to_ids.setdefault(e, []).append(i)

    adj: List[List[int]] = [[] for _ in range(len(visible))]
    for ids in edge_to_ids.values():
        if len(ids) < 2:
            continue
        a0 = ids[0]
        for b0 in ids[1:]:
            adj[a0].append(b0)
            adj[b0].append(a0)

    def _compute_figure_ids(cx0: float, cy0: float) -> set[int]:
        if not visible:
            return set()
        seed0 = min(
            range(len(visible)),
            key=lambda i: math.hypot(visible[i]["center"].real - cx0, visible[i]["center"].imag - cy0),
        )
        r_local = half * 0.46
        r_cap = half * 0.34
        scores: List[Tuple[float, int]] = []
        for i, r in enumerate(visible):
            dx0 = r["center"].real - cx0
            dy0 = r["center"].imag - cy0
            d0 = math.hypot(dx0, dy0)
            if d0 > r_local:
                continue
            s0 = _mask_val(dx0, dy0) - 0.40 * (d0 / max(r_local, 1e-9))
            scores.append((s0, i))
        scores.sort(reverse=True)
        target = int(150 + 80 * (tau5_norm[1] - 0.5))
        target = max(90, min(240, target))
        allowed = {i for _, i in scores[: max(target * 3, 260)]}
        if seed0 not in allowed and allowed:
            seed0 = min(
                allowed,
                key=lambda i: math.hypot(visible[i]["center"].real - cx0, visible[i]["center"].imag - cy0),
            )
        fig: set[int] = set()
        if seed0 not in allowed:
            return fig
        stack = [seed0]
        fig.add(seed0)
        while stack and len(fig) < target:
            cur = stack.pop()
            for nb in adj[cur]:
                if nb in fig or nb not in allowed:
                    continue
                dnb = math.hypot(visible[nb]["center"].real - cx0, visible[nb]["center"].imag - cy0)
                if dnb > r_cap:
                    continue
                fig.add(nb)
                stack.append(nb)
        return fig

    fig_ids = _compute_figure_ids(vp_x, vp_y)

    visited_pts: List[Tuple[float, float]] = []
    for block in (chain or []):
        bt = block.get("tau_vectors", [])
        if not isinstance(bt, list) or not bt:
            continue
        try:
            b5 = [(float(bt[k]) if k < len(bt) else 0.5) % 1.0 for k in range(5)]
        except (TypeError, ValueError):
            continue
        bdx, bdy = _tau_to_xy(b5)
        visited_pts.append((min(max(bdx * gain, -half * 0.32), half * 0.32), min(max(bdy * gain, -half * 0.32), half * 0.32)))

    fog_r = med_edge * 3.2

    def _is_visited_r(r: Dict[str, Any]) -> bool:
        if not visited_pts:
            return False
        cxr = r["center"].real
        cyr = r["center"].imag
        return any(math.hypot(cxr - vx, cyr - vy) <= fog_r for vx, vy in visited_pts)

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {SVG_WIDTH} {SVG_HEIGHT}" width="{SVG_WIDTH}" height="{SVG_HEIGHT}">',
        '  <rect width="100%" height="100%" fill="#0f172a"/>',
        '  <g id="tiles">',
    ]

    def _rgb(hex_color: str) -> Tuple[int, int, int]:
        h = hex_color.lstrip("#")
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

    def _mix(c1: str, c2: str, a: float) -> str:
        r1, g1, b1 = _rgb(c1)
        r2, g2, b2 = _rgb(c2)
        r_ = int(r1 * (1 - a) + r2 * a)
        g_ = int(g1 * (1 - a) + g2 * a)
        b_ = int(b1 * (1 - a) + b2 * a)
        return f"#{r_:02x}{g_:02x}{b_:02x}"

    def _shade_by_orientation_r(r: Dict[str, Any], base: str) -> str:
        v0, v1 = r["vertices"][0], r["vertices"][1]
        ang = math.atan2((v1 - v0).imag, (v1 - v0).real)
        k = (math.cos(ang - math.radians(35)) + 1.0) * 0.5
        a = 0.08 + 0.07 * k
        cxm = r["center"].real
        cym = r["center"].imag
        jitter = 0.035 * math.sin(cxm * 1.618 + cym * 1.414) + 0.03 * math.sin(cxm * 2.414 - cym * 1.732)
        a = min(0.22, max(0.03, a + jitter))
        return _mix(base, "#ffffff", a)

    for i, r in enumerate(visible):
        if i in fig_ids or _is_visited_r(r):
            continue
        base = "#1f4a73" if r["type"] == "thick" else "#193b5f"
        fill = _shade_by_orientation_r(r, base)
        path = _path_from_complex_verts(r["vertices"], cx_off, cy_off, scale)
        svg.append(f'    <path d="{path}" fill="{fill}" stroke="#0b223b" stroke-opacity="0.14" stroke-width="0.45"/>')

    for i, r in enumerate(visible):
        if i in fig_ids or not _is_visited_r(r):
            continue
        base = "#2f5f93" if r["type"] == "thick" else "#28507d"
        fill = _shade_by_orientation_r(r, base)
        path = _path_from_complex_verts(r["vertices"], cx_off, cy_off, scale)
        svg.append(f'    <path d="{path}" fill="{fill}" stroke="#12365a" stroke-opacity="0.18" stroke-width="0.45"/>')

    n_fig = 0
    for i, r in enumerate(visible):
        if i not in fig_ids:
            continue
        base = "#f59e0b" if r["type"] == "thick" else "#fbbf24"
        fill = _shade_by_orientation_r(r, base)
        path = _path_from_complex_verts(r["vertices"], cx_off, cy_off, scale)
        svg.append(f'    <path d="{path}" fill="{fill}" stroke="#d97706" stroke-opacity="0.65" stroke-width="0.65"/>')
        n_fig += 1

    # ── Genesis compass ──────────────────────────────────────────────────────
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
            f' <line x1="{mx:.1f}" y1="{my:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{g["col"]}" stroke-width="0.8" stroke-dasharray="3 3" opacity="0.6"/>'
        )
        ax = x2 - ux * 8 + uy * 4
        ay = y2 - uy * 8 - ux * 4
        bx = x2 - ux * 8 - uy * 4
        by = y2 - uy * 8 + ux * 4
        svg.append(
            f' <polygon points="{x2:.1f},{y2:.1f} {ax:.1f},{ay:.1f} {bx:.1f},{by:.1f}" fill="{g["col"]}" opacity="0.7"/>'
        )
        svg.append(
            f' <text x="{mx + ux * (rim + 14):.1f}" y="{my + uy * (rim + 14):.1f}" text-anchor="middle" fill="{g["col"]}" font-size="9" font-weight="bold">{g["label"]}</text>'
        )

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
                f' <text x="{SVG_CENTER_X}" y="16" text-anchor="middle" fill="#94a3b8" font-size="9">Global M · Chain={chain_len} · N={N} · {n_fig} figure tiles</text>',
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
