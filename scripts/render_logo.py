"""Generate the QuantRail mark: a railway in perspective that climbs like a price chart.

python scripts/render_logo.py  ->  assets/brand/quantrail-mark.svg, quantrail-badge.svg

Rails are tapered polygons offset from a price-like centreline with mitred corners;
crossties shrink and tighten with distance, which gives the track its depth.
"""

from __future__ import annotations

import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# A price path with real pullbacks: up, dip, up hard, dip, breakout.
PATH = [(6.0, 56.0), (21.0, 40.0), (29.0, 42.5), (42.0, 24.0), (48.0, 25.5), (58.0, 9.5)]
NEAR, FAR = 1.45, 0.30         # perspective scale at the start and at the end of the track
GAUGE, RAIL, TIE = 2.9, 1.7, 1.4


def _lengths(points):
    acc = [0.0]
    for (x0, y0), (x1, y1) in zip(points, points[1:], strict=False):
        acc.append(acc[-1] + math.hypot(x1 - x0, y1 - y0))
    return acc


def _scale(t):
    return NEAR + (FAR - NEAR) * t


def _offset(points, distance):
    """Mitred offset of a polyline; distance(i) gives the offset at vertex i."""
    out = []
    for i, (x, y) in enumerate(points):
        dirs = []
        if i > 0:
            px, py = points[i - 1]
            n = math.hypot(x - px, y - py)
            dirs.append(((x - px) / n, (y - py) / n))
        if i < len(points) - 1:
            nx, ny = points[i + 1]
            n = math.hypot(nx - x, ny - y)
            dirs.append(((nx - x) / n, (ny - y) / n))
        dx, dy = (sum(d[0] for d in dirs), sum(d[1] for d in dirs))
        n = math.hypot(dx, dy)
        dx, dy = dx / n, dy / n
        normal = (-dy, dx)
        # Miter length so both adjacent segments stay at the requested distance.
        seg = dirs[0]
        cos_half = abs(normal[0] * -seg[1] + normal[1] * seg[0]) or 1.0
        d = distance(i) / cos_half
        out.append((x + normal[0] * d, y + normal[1] * d))
    return out


def _poly(points):
    return "M" + " L".join(f"{x:.2f} {y:.2f}" for x, y in points) + " Z"


def rails(path):
    total = _lengths(path)
    ts = [length / total[-1] for length in total]
    paths = []
    for side in (-1, 1):
        outer = _offset(path, lambda i, s=side: s * (GAUGE + RAIL / 2) * _scale(ts[i]))
        inner = _offset(path, lambda i, s=side: s * (GAUGE - RAIL / 2) * _scale(ts[i]))
        paths.append(_poly(outer + inner[::-1]))
    return paths


def ties(path):
    total = _lengths(path)
    length = total[-1]
    shapes, s = [], 3.0
    while s < length - 2:
        t = s / length
        k = _scale(t)
        seg = max(i for i in range(len(path) - 1) if total[i] <= s)
        (x0, y0), (x1, y1) = path[seg], path[seg + 1]
        n = math.hypot(x1 - x0, y1 - y0)
        ux, uy = (x1 - x0) / n, (y1 - y0) / n
        near_corner = min(s - total[seg], total[seg + 1] - s) < 1.6 * k
        if not near_corner:
            f = (s - total[seg]) / n
            cx, cy = x0 + (x1 - x0) * f, y0 + (y1 - y0) * f
            half_len, half_w = (GAUGE + RAIL) * 1.3 * k, TIE * k / 2
            nx, ny = -uy, ux
            corners = [(cx + nx * half_len + ux * half_w, cy + ny * half_len + uy * half_w),
                       (cx - nx * half_len + ux * half_w, cy - ny * half_len + uy * half_w),
                       (cx - nx * half_len - ux * half_w, cy - ny * half_len - uy * half_w),
                       (cx + nx * half_len - ux * half_w, cy + ny * half_len - uy * half_w)]
            shapes.append(_poly(corners))
        s += 4.2 * k
    return shapes


def spark(cx, cy, r):
    """A sharp four-point star: the latest print."""
    pts = []
    for i in range(8):
        a = math.pi / 4 * i - math.pi / 2
        rr = r if i % 2 == 0 else r * 0.28
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    return _poly(pts)


def svg(*, badge: bool) -> str:
    # The badge lets the track enter from beyond the frame, which gives it its rush.
    path = [(-6.0, 70.0)] + PATH[1:] if badge else PATH
    rail_paths = "\n    ".join(f'<path d="{p}"/>' for p in rails(path))
    tie_paths = "\n    ".join(f'<path d="{p}"/>' for p in ties(path))
    ex, ey = path[-1]
    if badge:
        bg = '<rect width="64" height="64" rx="9" fill="url(#bg)"/>'
        frame = ('<rect x="0.5" y="0.5" width="63" height="63" rx="8.5" fill="none" stroke="#14B8A6" '
                 'stroke-opacity="0.45"/>')
        rail_fill, tie_fill = "url(#steel)", "#64748B"
        defs = '''<linearGradient id="bg" x1="0" y1="64" x2="64" y2="0" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="#020617"/><stop offset="1" stop-color="#0F2A2E"/></linearGradient>
    <linearGradient id="steel" x1="5" y1="57" x2="58" y2="9" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="#F8FAFC"/><stop offset="0.55" stop-color="#99F6E4"/>
      <stop offset="1" stop-color="#2DD4BF"/></linearGradient>
    <clipPath id="frame"><rect width="64" height="64" rx="9"/></clipPath>'''
    else:
        bg = frame = ""
        rail_fill, tie_fill = "url(#steel)", "#94A3B8"
        defs = '''<linearGradient id="steel" x1="5" y1="57" x2="58" y2="9" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="#0F766E"/><stop offset="1" stop-color="#2DD4BF"/></linearGradient>'''
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" role="img" aria-label="QuantRail">
  <title>QuantRail</title>
  <defs>
    {defs}
    <radialGradient id="glow" cx="{ex}" cy="{ey}" r="9" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="#F59E0B" stop-opacity="0.55"/>
      <stop offset="1" stop-color="#F59E0B" stop-opacity="0"/>
    </radialGradient>
  </defs>
  {bg}
  <g{' clip-path="url(#frame)"' if badge else ''}>
  <g fill="{tie_fill}">
    {tie_paths}
  </g>
  <g fill="{rail_fill}">
    {rail_paths}
  </g>
  </g>
  {frame}
  <circle cx="{ex}" cy="{ey}" r="9" fill="url(#glow)"/>
  <path d="{spark(ex, ey, 5.2)}" fill="#FBBF24"/>
</svg>
'''


def main() -> None:
    out = ROOT / "assets" / "brand"
    out.mkdir(parents=True, exist_ok=True)
    (out / "quantrail-mark.svg").write_text(svg(badge=False), encoding="utf-8")
    (out / "quantrail-badge.svg").write_text(svg(badge=True), encoding="utf-8")
    print("wrote assets/brand/quantrail-mark.svg and quantrail-badge.svg")


if __name__ == "__main__":
    main()
