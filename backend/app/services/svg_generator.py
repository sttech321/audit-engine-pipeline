"""
SVG Penrose patch visualization service.

PASS97 Spec Compliant:
- Generates SVG representation of Penrose P3 tiling
- Visual audit fingerprint
- Embeddable in PDF reports and NFT metadata

The Penrose P3 tiling provides a quasiperiodic visual representation
of the audit state that is unique to each audited file.
"""
import math
from typing import Dict, Any, List, Tuple


# ─── Penrose P3 Constants ────────────────────────────────────────────────────

PHI = (1 + math.sqrt(5)) / 2  # Golden ratio ≈ 1.618
PI = math.pi
TWO_PI = 2 * PI
PENTAGRID_SECTORS = 5

# SVG dimensions
SVG_WIDTH = 400
SVG_HEIGHT = 400
SVG_CENTER_X = SVG_WIDTH / 2
SVG_CENTER_Y = SVG_HEIGHT / 2

# Tile colors based on sector
SECTOR_COLORS = [
    "#3b82f6",  # Blue (sector 0)
    "#8b5cf6",  # Purple (sector 1)
    "#ec4899",  # Pink (sector 2)
    "#f97316",  # Orange (sector 3)
    "#22c55e",  # Green (sector 4)
]

# Risk level colors
RISK_COLORS = {
    "LOW": "#22c55e",
    "MEDIUM": "#eab308",
    "HIGH": "#f97316",
    "CRITICAL": "#ef4444",
}


def _rotate_point(x: float, y: float, angle: float, cx: float = 0, cy: float = 0) -> Tuple[float, float]:
    """Rotate a point around a center."""
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    dx = x - cx
    dy = y - cy
    return (
        cx + dx * cos_a - dy * sin_a,
        cy + dx * sin_a + dy * cos_a
    )


def _generate_thin_rhombus(cx: float, cy: float, scale: float, angle: float) -> str:
    """Generate SVG path for a thin Penrose rhombus (36° angles)."""
    # Thin rhombus has angles of 36° and 144°
    half_diag_long = scale * PHI
    half_diag_short = scale * 0.5
    
    # Vertices before rotation
    points = [
        (cx, cy - half_diag_short),  # Top
        (cx + half_diag_long, cy),    # Right
        (cx, cy + half_diag_short),  # Bottom
        (cx - half_diag_long, cy),    # Left
    ]
    
    # Rotate all points
    rotated = [_rotate_point(px, py, angle, cx, cy) for px, py in points]
    
    # Create SVG path
    path_data = f"M {rotated[0][0]:.2f},{rotated[0][1]:.2f}"
    for px, py in rotated[1:]:
        path_data += f" L {px:.2f},{py:.2f}"
    path_data += " Z"
    
    return path_data


def _generate_thick_rhombus(cx: float, cy: float, scale: float, angle: float) -> str:
    """Generate SVG path for a thick Penrose rhombus (72° angles)."""
    # Thick rhombus has angles of 72° and 108°
    half_diag = scale
    
    # Vertices before rotation (square-ish but with golden ratio)
    points = [
        (cx, cy - half_diag),
        (cx + half_diag * 0.8, cy),
        (cx, cy + half_diag),
        (cx - half_diag * 0.8, cy),
    ]
    
    # Rotate all points
    rotated = [_rotate_point(px, py, angle, cx, cy) for px, py in points]
    
    # Create SVG path
    path_data = f"M {rotated[0][0]:.2f},{rotated[0][1]:.2f}"
    for px, py in rotated[1:]:
        path_data += f" L {px:.2f},{py:.2f}"
    path_data += " Z"
    
    return path_data


def generate_penrose_svg(
    penrose_data: Dict[str, Any],
    risk_level: str = "LOW",
    show_labels: bool = True,
    show_hash: bool = True
) -> str:
    """
    Generate SVG visualization of Penrose P3 tiling from audit data.
    
    Args:
        penrose_data: Dictionary with r, theta, sector, penrose_hash, tau, tile_hash
        risk_level: Risk level for coloring (LOW, MEDIUM, HIGH, CRITICAL)
        show_labels: Whether to show sector labels
        show_hash: Whether to show truncated hash
        
    Returns:
        SVG string
    """
    r = penrose_data.get("r", 0.5)
    theta = penrose_data.get("theta", 0)
    sector = penrose_data.get("sector", 0)
    penrose_hash = penrose_data.get("penrose_hash", "")[:16]
    tau = penrose_data.get("tau", 0.5)
    tile_hash = penrose_data.get("tile_hash", "")[:8]
    
    # Base scale from r value
    base_scale = 30 + r * 50
    
    # Get colors
    sector_color = SECTOR_COLORS[sector % len(SECTOR_COLORS)]
    risk_color = RISK_COLORS.get(risk_level, RISK_COLORS["LOW"])
    
    # Start SVG
    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {SVG_WIDTH} {SVG_HEIGHT}" width="{SVG_WIDTH}" height="{SVG_HEIGHT}">',
        f'  <defs>',
        f'    <linearGradient id="bgGrad" x1="0%" y1="0%" x2="100%" y2="100%">',
        f'      <stop offset="0%" style="stop-color:#0f172a;stop-opacity:1" />',
        f'      <stop offset="100%" style="stop-color:#1e293b;stop-opacity:1" />',
        f'    </linearGradient>',
        f'    <filter id="glow">',
        f'      <feGaussianBlur stdDeviation="2" result="coloredBlur"/>',
        f'      <feMerge><feMergeNode in="coloredBlur"/><feMergeNode in="SourceGraphic"/></feMerge>',
        f'    </filter>',
        f'  </defs>',
        f'  <rect width="100%" height="100%" fill="url(#bgGrad)"/>',
    ]
    
    # Generate central pentagonal structure
    # Draw 5 sectors with different tiles
    for k in range(PENTAGRID_SECTORS):
        angle_k = k * TWO_PI / PENTAGRID_SECTORS
        
        # Position tiles at pentagrid angles
        tile_cx = SVG_CENTER_X + math.cos(angle_k) * base_scale * 1.5
        tile_cy = SVG_CENTER_Y + math.sin(angle_k) * base_scale * 1.5
        
        # Alternate between thin and thick rhombi
        if k == sector:
            # Highlight the active sector
            path = _generate_thick_rhombus(tile_cx, tile_cy, base_scale * 0.8, angle_k)
            color = sector_color
            opacity = 0.9
            stroke_width = 2
        else:
            path = _generate_thin_rhombus(tile_cx, tile_cy, base_scale * 0.5, angle_k)
            color = "#475569"
            opacity = 0.5
            stroke_width = 1
        
        svg_parts.append(
            f'  <path d="{path}" fill="{color}" fill-opacity="{opacity}" '
            f'stroke="#94a3b8" stroke-width="{stroke_width}" filter="url(#glow)"/>'
        )
    
    # Draw central marker based on tau
    center_radius = 10 + tau * 20
    svg_parts.append(
        f'  <circle cx="{SVG_CENTER_X}" cy="{SVG_CENTER_Y}" r="{center_radius}" '
        f'fill="{risk_color}" fill-opacity="0.8" stroke="white" stroke-width="2"/>'
    )
    
    # Draw connecting lines (pentagrid structure)
    for k in range(PENTAGRID_SECTORS):
        angle_k = k * TWO_PI / PENTAGRID_SECTORS
        end_x = SVG_CENTER_X + math.cos(angle_k) * (base_scale * 2.5)
        end_y = SVG_CENTER_Y + math.sin(angle_k) * (base_scale * 2.5)
        svg_parts.append(
            f'  <line x1="{SVG_CENTER_X}" y1="{SVG_CENTER_Y}" '
            f'x2="{end_x:.2f}" y2="{end_y:.2f}" '
            f'stroke="#64748b" stroke-width="1" stroke-opacity="0.4" stroke-dasharray="4,4"/>'
        )
    
    # Add labels
    if show_labels:
        svg_parts.append(
            f'  <text x="{SVG_CENTER_X}" y="30" text-anchor="middle" '
            f'fill="#e2e8f0" font-family="monospace" font-size="14" font-weight="bold">'
            f'Penrose P3 Sector {sector}</text>'
        )
        svg_parts.append(
            f'  <text x="{SVG_CENTER_X}" y="{SVG_HEIGHT - 40}" text-anchor="middle" '
            f'fill="#94a3b8" font-family="monospace" font-size="10">'
            f'τ = {tau:.6f} | θ = {theta:.4f}</text>'
        )
    
    if show_hash:
        svg_parts.append(
            f'  <text x="{SVG_CENTER_X}" y="{SVG_HEIGHT - 20}" text-anchor="middle" '
            f'fill="#64748b" font-family="monospace" font-size="9">'
            f'{penrose_hash}…</text>'
        )
    
    # Risk badge
    badge_x = SVG_WIDTH - 60
    badge_y = 25
    svg_parts.append(
        f'  <rect x="{badge_x - 35}" y="{badge_y - 12}" width="70" height="20" rx="10" '
        f'fill="{risk_color}" fill-opacity="0.9"/>'
    )
    svg_parts.append(
        f'  <text x="{badge_x}" y="{badge_y + 4}" text-anchor="middle" '
        f'fill="white" font-family="sans-serif" font-size="10" font-weight="bold">'
        f'{risk_level}</text>'
    )
    
    svg_parts.append('</svg>')
    
    return '\n'.join(svg_parts)


def generate_minimal_svg(
    sector: int,
    risk_level: str = "LOW",
    size: int = 64
) -> str:
    """
    Generate a minimal SVG icon for the Penrose sector.
    
    Suitable for small thumbnails or icons.
    
    Args:
        sector: Pentagrid sector (0-4)
        risk_level: Risk level for coloring
        size: SVG size in pixels
        
    Returns:
        SVG string
    """
    color = SECTOR_COLORS[sector % len(SECTOR_COLORS)]
    cx, cy = size / 2, size / 2
    r = size * 0.35
    
    # Draw a pentagon with highlighted sector
    points = []
    for k in range(5):
        angle = k * TWO_PI / 5 - PI / 2  # Start from top
        px = cx + r * math.cos(angle)
        py = cy + r * math.sin(angle)
        points.append(f"{px:.1f},{py:.1f}")
    
    polygon_points = " ".join(points)
    
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" width="{size}" height="{size}">
  <polygon points="{polygon_points}" fill="{color}" fill-opacity="0.8" stroke="#fff" stroke-width="2"/>
  <text x="{cx}" y="{cy + 4}" text-anchor="middle" fill="white" font-family="sans-serif" font-size="{size // 4}" font-weight="bold">{sector}</text>
</svg>'''


def embed_svg_in_metadata(svg_content: str) -> Dict[str, Any]:
    """
    Prepare SVG for embedding in NFT metadata.
    
    Args:
        svg_content: Raw SVG string
        
    Returns:
        Dictionary with image data URI and metadata
    """
    import base64
    
    # Encode SVG as base64 data URI
    svg_bytes = svg_content.encode('utf-8')
    b64_svg = base64.b64encode(svg_bytes).decode('ascii')
    data_uri = f"data:image/svg+xml;base64,{b64_svg}"
    
    return {
        "image": data_uri,
        "image_type": "image/svg+xml",
        "image_encoding": "base64"
    }
