"""Animated isometric architecture diagram: python scripts/render_architecture.py

Layers are stacked plates; data packets rise through them and each plate lights up as
a packet passes, ending at the result on top. CSS animations only, disabled under
prefers-reduced-motion. Self-contained dark card so it reads the same on any theme.
"""

from __future__ import annotations

import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
W, H = 960, 700
CX, CY, S = 290, 505, 19          # isometric origin and scale
SIZE, THICK, GAP = 7.2, 0.8, 3.9   # plate size, thickness and vertical spacing (model units)
CYCLE = 4.8                        # seconds for one packet to climb the stack

LAYERS = [  # bottom to top: (title, subtitle, top colour, side colour, edge colour)
    ("core", "instruments · Decimal quantities · money · provenance",
     "#134E4A", "#0B2F2C", "#2DD4BF"),
    ("data", "ingest · versions · manifests · trust flags",
     "#115E59", "#0B3B38", "#2DD4BF"),
    ("accounting · markets", "ledger · settlement · tw_equity · crypto (planned)",
     "#0F766E", "#0A4A45", "#5EEAD4"),
    ("engine", "decisions → orders → fills · daily NAV identity",
     "#0F766E", "#0A4A45", "#5EEAD4"),
    ("research · stats", "trial registry · contracts · bootstrap · DSR · PBO",
     "#14B8A6", "#0D7A70", "#99F6E4"),
    ("result + trust report", "every number, plus what could not be verified",
     "#D97706", "#92400E", "#FCD34D"),
]


def iso(x, y, z):
    return (CX + (x - y) * math.cos(math.pi / 6) * S, CY + (x + y) * math.sin(math.pi / 6) * S - z * S)


def poly(points):
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in points)


def plate(i, layer):
    title, subtitle, top, side, edge = layer
    z = i * GAP
    t = z + THICK
    top_face = [iso(0, 0, t), iso(SIZE, 0, t), iso(SIZE, SIZE, t), iso(0, SIZE, t)]
    front = [iso(0, SIZE, t), iso(SIZE, SIZE, t), iso(SIZE, SIZE, z), iso(0, SIZE, z)]
    right = [iso(SIZE, 0, t), iso(SIZE, SIZE, t), iso(SIZE, SIZE, z), iso(SIZE, 0, z)]
    delay = CYCLE * (i + 0.5) / (len(LAYERS) + 0.5)
    anchor = iso(SIZE, 0, t)                      # right corner of the plate, for the leader line
    label_y = anchor[1] + 4
    text_x = 570
    return f'''
  <g class="plate">
    <polygon points="{poly(front)}" fill="{side}"/>
    <polygon points="{poly(right)}" fill="{side}" opacity="0.8"/>
    <polygon points="{poly(top_face)}" fill="{top}"/>
    <polygon class="glow" style="animation-delay:{delay:.2f}s" points="{poly(top_face)}"
             fill="{edge}" fill-opacity="0.28" stroke="{edge}" stroke-width="3"/>
    <line x1="{anchor[0] + 6:.1f}" y1="{anchor[1]:.1f}" x2="{text_x - 12}" y2="{label_y - 4:.1f}"
          stroke="#334155" stroke-dasharray="3 4"/>
    <text x="{text_x}" y="{label_y:.1f}" class="t" fill="{edge}">{title}</text>
    <text x="{text_x}" y="{label_y + 19:.1f}" class="s">{subtitle}</text>
  </g>'''


def packets():
    bottom = iso(SIZE / 2, SIZE / 2, -2.2)
    top = iso(SIZE / 2, SIZE / 2, (len(LAYERS) - 1) * GAP + THICK + 0.2)
    rise = bottom[1] - top[1]
    beam = f'''<line x1="{bottom[0]:.1f}" y1="{bottom[1]:.1f}" x2="{top[0]:.1f}" y2="{top[1]:.1f}"
        stroke="url(#beam)" stroke-width="3"/>'''
    dots = "\n  ".join(
        f'<g class="packet" style="animation-delay:{k * CYCLE / 3:.2f}s">'
        f'<circle cx="{bottom[0]:.1f}" cy="{bottom[1]:.1f}" r="16" fill="url(#halo)"/>'
        f'<circle cx="{bottom[0]:.1f}" cy="{bottom[1]:.1f}" r="6.5" fill="#FDE68A"/></g>' for k in range(3))
    return beam, dots, rise, top


def spark(cx, cy, r):
    pts = []
    for i in range(8):
        a = math.pi / 4 * i - math.pi / 2
        rr = r if i % 2 == 0 else r * 0.28
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    return poly(pts)


def render() -> str:
    beam, dots, rise, top = packets()
    plates = "".join(plate(i, layer) for i, layer in enumerate(LAYERS))
    star_y = top[1] - 26
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img"
     aria-label="QuantRail architecture: data rises through core, data governance, accounting and markets,
     the engine and research and statistics into a result with a trust report">
  <title>QuantRail architecture</title>
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="{W}" y2="{H}" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="#020617"/><stop offset="1" stop-color="#0F2A2E"/>
    </linearGradient>
    <linearGradient id="beam" x1="0" y1="1" x2="0" y2="0">
      <stop offset="0" stop-color="#F59E0B" stop-opacity="0"/><stop offset="1" stop-color="#F59E0B" stop-opacity="0.7"/>
    </linearGradient>
    <radialGradient id="halo"><stop offset="0" stop-color="#F59E0B" stop-opacity="0.6"/>
      <stop offset="1" stop-color="#F59E0B" stop-opacity="0"/></radialGradient>
    <pattern id="grid" width="32" height="32" patternUnits="userSpaceOnUse">
      <path d="M32 0 H0 V32" fill="none" stroke="#14B8A6" stroke-opacity="0.07"/>
    </pattern>
    <style>
      .t {{ font: 700 17px -apple-system, "Segoe UI", Helvetica, Arial, sans-serif; }}
      .s {{ font: 13px -apple-system, "Segoe UI", Helvetica, Arial, sans-serif; fill: #94A3B8; }}
      .h {{ font: 800 13px -apple-system, "Segoe UI", Helvetica, Arial, sans-serif; fill: #5EEAD4;
            letter-spacing: 3px; }}
      .glow {{ opacity: 0; animation: glow {CYCLE}s ease-out infinite; }}
      .packet {{ opacity: 0; animation: rise {CYCLE}s cubic-bezier(.45,.05,.55,.95) infinite; }}
      .pulse {{ animation: pulse {CYCLE}s ease-in-out infinite; transform-box: fill-box; transform-origin: center; }}
      @keyframes glow {{ 0% {{ opacity: 0; }} 6% {{ opacity: 1; }} 40% {{ opacity: 0; }} 100% {{ opacity: 0; }} }}
      @keyframes rise {{ 0% {{ opacity: 0; transform: translateY(0); }} 8% {{ opacity: 1; }}
                        88% {{ opacity: 1; }} 100% {{ opacity: 0; transform: translateY(-{rise:.1f}px); }} }}
      @keyframes pulse {{ 0%, 70% {{ transform: scale(1); opacity: .85; }} 85% {{ transform: scale(1.35); opacity: 1; }}
                         100% {{ transform: scale(1); opacity: .85; }} }}
      @media (prefers-reduced-motion: reduce) {{
        .glow, .packet, .pulse {{ animation: none; }} .glow {{ opacity: .35; }} .packet {{ opacity: 0; }}
      }}
    </style>
  </defs>
  <rect width="{W}" height="{H}" rx="18" fill="url(#bg)"/>
  <rect width="{W}" height="{H}" rx="18" fill="url(#grid)"/>
  <text x="40" y="52" class="h">QUANTRAIL · ARCHITECTURE</text>
  <text x="{CX}" y="{H - 22}" text-anchor="middle" class="s">▲ your data · CSV · Parquet · adapters</text>
  {beam}
  {plates}
  {dots}
  <circle cx="{top[0]:.1f}" cy="{star_y:.1f}" r="26" fill="url(#halo)"/>
  <polygon class="pulse" points="{spark(top[0], star_y, 13)}" fill="#FBBF24"/>
</svg>
'''


def main() -> None:
    (ROOT / "assets" / "architecture.svg").write_text(render(), encoding="utf-8")
    print("wrote assets/architecture.svg")


if __name__ == "__main__":
    main()
