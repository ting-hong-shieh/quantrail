"""Animated architecture flow: python scripts/render_architecture.py

The diagram keeps the information of a flowchart (what flows where, what supports the
engine, which auxiliary tools accompany the result); the animation encodes the same story. A data packet
rides the rails from your data to the result, passing behind each box as it is
processed; each box lights up as the packet reaches it, the supporting arrows light when it reaches the engine, and the auxiliary-tool
arrows light when it reaches the result. Disabled under prefers-reduced-motion.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
W, H = 960, 470
CYCLE = 5.0                  # seconds per packet trip
TRAVEL = 0.62                # share of the cycle spent travelling
ROW_Y, BOX_H = 92, 78        # main flow row
FONT = '-apple-system, "Segoe UI", Helvetica, Arial, sans-serif'

# (key, x, width, title, line 1, line 2, accent)
FLOW = [
    ("src", 24, 168, "your data", "CSV · Parquet · adapters", "", "#64748B"),
    ("data", 234, 200, "data", "ingest · versions · manifests", "provenance · trust flags", "#2DD4BF"),
    ("engine", 476, 210, "engine", "decisions → orders → fills", "daily NAV identity", "#2DD4BF"),
    ("result", 728, 208, "result", "ledger · orders · events", "+ trust report", "#F59E0B"),
]
X0 = FLOW[0][1] + FLOW[0][2] / 2
X1 = FLOW[-1][1] + FLOW[-1][2] / 2


def arrival(cx: float) -> float:
    """Seconds after cycle start at which the packet reaches x = cx."""
    return (cx - X0) / (X1 - X0) * TRAVEL * CYCLE


def box(x, y, w, h, title, l1, l2, accent, *, dashed=False, delay=None):
    stroke = f'stroke="{accent}" stroke-width="1.5"' + (' stroke-dasharray="6 5"' if dashed else "")
    fill = "#020617" if dashed else "#0B1F24"   # opaque, so the packet passes behind boxes
    title_fill = "#94A3B8" if dashed else accent
    pulse = (f'<rect class="lit" style="animation-delay:{delay:.2f}s" x="{x}" y="{y}" width="{w}" height="{h}" '
             f'rx="12" fill="{accent}" fill-opacity="0.16" stroke="{accent}" stroke-width="3"/>') if delay is not None else ""
    lines = f'<text class="s" x="{x + w / 2}" y="{y + 50}" text-anchor="middle">{l1}</text>'
    if l2:
        lines += f'<text class="s" x="{x + w / 2}" y="{y + 67}" text-anchor="middle">{l2}</text>'
    return f'''<g>
    <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="{fill}" {stroke}/>
    {pulse}
    <text class="t" x="{x + w / 2}" y="{y + 29}" text-anchor="middle" fill="{title_fill}">{title}</text>
    {lines}
  </g>'''


def rail(x1, x2, y):
    """A short stretch of track between two boxes."""
    ties = "".join(f'<line x1="{x}" y1="{y - 7}" x2="{x}" y2="{y + 7}"/>' for x in range(int(x1) + 6, int(x2) - 3, 8))
    return f'''<g stroke="#334155" stroke-width="2.5">{ties}</g>
  <g stroke="#94A3B8" stroke-width="2"><line x1="{x1}" y1="{y - 4}" x2="{x2}" y2="{y - 4}"/>
    <line x1="{x1}" y1="{y + 4}" x2="{x2}" y2="{y + 4}"/></g>'''


def arrow(x1, y1, x2, y2, delay):
    return f'''<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#475569" stroke-width="2" marker-end="url(#head)"/>
  <line class="lit" style="animation-delay:{delay:.2f}s" x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}"
        stroke="#5EEAD4" stroke-width="3" marker-end="url(#headlit)"/>'''


def render() -> str:
    y_mid = ROW_Y + BOX_H / 2
    parts = []
    for i, (key, x, w, title, l1, l2, accent) in enumerate(FLOW):
        delay = None if key == "src" else arrival(x + w / 2) - 0.15
        parts.append(box(x, ROW_Y, w, BOX_H, title, l1, l2, accent, dashed=key == "src", delay=delay))
        if i < len(FLOW) - 1:
            parts.append(rail(x + w, FLOW[i + 1][1], y_mid))
    engine = FLOW[2]
    result = FLOW[3]
    t_engine = arrival(engine[1] + engine[2] / 2) - 0.3
    t_result = arrival(result[1] + result[2] / 2) - 0.1
    row2 = 228
    # Supporting modules under the engine.
    parts.append(box(400, row2, 160, BOX_H, "accounting", "multi-currency ledger", "settlement · events",
                     "#2DD4BF", delay=t_engine))
    parts.append(f'''<g>
    <rect x="580" y="{row2}" width="186" height="{BOX_H}" rx="12" fill="#0B1F24" stroke="#2DD4BF" stroke-width="1.5"/>
    <rect class="lit" style="animation-delay:{t_engine:.2f}s" x="580" y="{row2}" width="186" height="{BOX_H}" rx="12"
          fill="#2DD4BF" fill-opacity="0.16" stroke="#2DD4BF" stroke-width="3"/>
    <text class="t" x="673" y="{row2 + 29}" text-anchor="middle" fill="#2DD4BF">markets</text>
    <rect x="594" y="{row2 + 42}" width="80" height="24" rx="12" fill="#115E59"/>
    <text class="c" x="634" y="{row2 + 58}" text-anchor="middle">tw_equity</text>
    <rect x="682" y="{row2 + 42}" width="72" height="24" rx="12" fill="none" stroke="#64748B" stroke-dasharray="4 3"/>
    <text class="c" x="718" y="{row2 + 58}" text-anchor="middle" fill="#94A3B8">crypto…</text>
  </g>''')
    parts.append(arrow(480, row2, 545, ROW_Y + BOX_H + 6, t_engine))
    parts.append(arrow(673, row2, 625, ROW_Y + BOX_H + 6, t_engine))
    # Auxiliary research tools.
    parts.append(box(786, row2, 150, BOX_H, "research", "trial registry", "auxiliary tool",
                     "#99F6E4", delay=t_result))
    parts.append(box(786, row2 + 104, 150, BOX_H, "stats", "metrics · bootstrap", "Holm · DSR · PBO",
                     "#99F6E4", delay=t_result))
    parts.append(arrow(861, row2, 861, ROW_Y + BOX_H + 6, t_result))
    parts.append(arrow(861, row2 + 104, 861, row2 + BOX_H + 6, t_result))
    # Foundation.
    core_y = H - 66
    parts.append(f'''<rect x="24" y="{core_y}" width="742" height="42" rx="12" fill="#0B2F2C" stroke="#134E4A"/>
  <text class="t" x="44" y="{core_y + 27}" fill="#5EEAD4">core</text>
  <text class="s" x="96" y="{core_y + 27}">instruments · Decimal quantities · money per currency · provenance · trust flags</text>''')
    travel_px = X1 - X0
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img"
     aria-label="QuantRail architecture: your data flows through data governance and the engine into a result with a trust report; accounting and market modules support the engine; research and statistics provide auxiliary tools for recording trials and analysing results; core types underlie everything">
  <title>QuantRail architecture</title>
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="{W}" y2="{H}" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="#020617"/><stop offset="1" stop-color="#0F2A2E"/>
    </linearGradient>
    <pattern id="grid" width="32" height="32" patternUnits="userSpaceOnUse">
      <path d="M32 0 H0 V32" fill="none" stroke="#14B8A6" stroke-opacity="0.06"/>
    </pattern>
    <radialGradient id="halo"><stop offset="0" stop-color="#F59E0B" stop-opacity="0.7"/>
      <stop offset="1" stop-color="#F59E0B" stop-opacity="0"/></radialGradient>
    <marker id="head" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M0 0 L10 5 L0 10 z" fill="#475569"/></marker>
    <marker id="headlit" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M0 0 L10 5 L0 10 z" fill="#5EEAD4"/></marker>
    <style>
      .t {{ font: 700 16px {FONT}; }}
      .s {{ font: 12.5px {FONT}; fill: #94A3B8; }}
      .c {{ font: 600 12px {FONT}; fill: #F8FAFC; }}
      .h {{ font: 800 12px {FONT}; fill: #5EEAD4; letter-spacing: 3px; }}
      .lit {{ opacity: 0; animation: lit {CYCLE}s ease-out infinite; }}
      .packet {{ animation: ride {CYCLE}s cubic-bezier(.5,0,.5,1) infinite; }}
      @keyframes lit {{ 0% {{ opacity: 0; }} 4% {{ opacity: 1; }} 30% {{ opacity: 0; }} 100% {{ opacity: 0; }} }}
      @keyframes ride {{ 0% {{ transform: translateX(0); opacity: 0; }} 4% {{ opacity: 1; }}
        {TRAVEL * 100:.0f}% {{ transform: translateX({travel_px:.0f}px); opacity: 1; }}
        {TRAVEL * 100 + 8:.0f}%, 100% {{ transform: translateX({travel_px:.0f}px); opacity: 0; }} }}
      @media (prefers-reduced-motion: reduce) {{ .lit, .packet {{ animation: none; }} .packet {{ opacity: 0; }} }}
    </style>
  </defs>
  <rect width="{W}" height="{H}" rx="18" fill="url(#bg)"/>
  <rect width="{W}" height="{H}" rx="18" fill="url(#grid)"/>
  <text class="h" x="28" y="50">QUANTRAIL · ARCHITECTURE</text>
  <g class="packet"><circle cx="{X0}" cy="{y_mid}" r="17" fill="url(#halo)"/>
    <circle cx="{X0}" cy="{y_mid}" r="6.5" fill="#FDE68A"/></g>
  {chr(10).join("  " + p for p in parts).strip()}
</svg>
'''


def main() -> None:
    (ROOT / "assets" / "architecture.svg").write_text(render(), encoding="utf-8")
    print("wrote assets/architecture.svg")


if __name__ == "__main__":
    main()
