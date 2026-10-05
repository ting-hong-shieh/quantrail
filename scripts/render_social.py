"""Social preview (1280x640): python scripts/render_social.py [path-to-chrome]

Writes assets/social-preview.html and, when a Chromium binary is given or found on
PATH, renders assets/social-preview.png from it. The track reuses the logo geometry.
"""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("render_logo", ROOT / "scripts" / "render_logo.py")
logo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(logo)

# Model units are scaled by 10: the canvas is 128 x 64 units. The track enters from
# below the frame and breaks out near the top-right corner.
TRACK = [(56.0, 74.0), (80.0, 47.0), (90.0, 51.0), (106.0, 27.0), (113.0, 30.0), (124.5, 8.5)]


def track_svg() -> str:
    rails = "\n".join(f'<path d="{p}"/>' for p in logo.rails(TRACK))
    ties = "\n".join(f'<path d="{p}"/>' for p in logo.ties(TRACK))
    ex, ey = TRACK[-1]
    return f'''<svg class="track" viewBox="0 0 128 64" preserveAspectRatio="xMidYMid slice"
     xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="steel" x1="56" y1="74" x2="124" y2="8" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="#F8FAFC"/><stop offset="0.5" stop-color="#99F6E4"/>
      <stop offset="1" stop-color="#2DD4BF"/></linearGradient>
    <radialGradient id="glow" cx="{ex}" cy="{ey}" r="14" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="#F59E0B" stop-opacity="0.8"/><stop offset="1" stop-color="#F59E0B" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <g fill="#334155">{ties}</g>
  <g fill="url(#steel)">{rails}</g>
  <circle cx="{ex}" cy="{ey}" r="14" fill="url(#glow)"/>
  <path d="{logo.spark(ex, ey, 5.5)}" fill="#FBBF24"/>
</svg>'''


def html() -> str:
    return f'''<!doctype html><html><head><meta charset="utf-8"><style>
html,body{{margin:0}}
body{{width:1280px;height:640px;overflow:hidden;position:relative;font-family:Inter,Helvetica,Arial,sans-serif;
  background:radial-gradient(circle at 85% 10%,#0F3B3A 0,#020617 55%);color:#F8FAFC}}
.grid{{position:absolute;inset:0;background-image:linear-gradient(#14B8A611 1px,transparent 1px),
  linear-gradient(90deg,#14B8A611 1px,transparent 1px);background-size:40px 40px}}
.track{{position:absolute;inset:0;width:1280px;height:640px}}
.brand{{position:absolute;left:72px;top:58px;display:flex;align-items:center;gap:16px;font-size:30px;font-weight:800}}
.brand img{{width:52px}}
h1{{position:absolute;left:72px;top:140px;margin:0;font-size:70px;line-height:1.03;letter-spacing:-2px;font-weight:900}}
h1 span{{display:block;margin-top:10px;color:#5EEAD4;font-size:50px;letter-spacing:-1px}}
ul{{position:absolute;left:72px;top:398px;margin:0;padding:0;list-style:none;font-size:26px;line-height:1.75;color:#CBD5E1}}
li::before{{content:"▸ ";color:#F59E0B}}
.url{{position:absolute;left:72px;bottom:44px;font-size:21px;color:#64748B;font-family:'DejaVu Sans Mono',monospace}}
</style></head><body>
<div class="grid"></div>
{track_svg()}
<div class="brand"><img src="brand/quantrail-badge.svg">QuantRail</div>
<h1>Every backtest<br>lies a little.<span>QuantRail tells you where.</span></h1>
<ul><li>Ledger-accurate to the cent</li><li>Point-in-time, licence-aware data</li><li>Overfitting, measured</li></ul>
<div class="url">github.com/ting-hong-shieh/quantrail</div>
</body></html>'''


def main() -> None:
    page = ROOT / "assets" / "social-preview.html"
    page.write_text(html(), encoding="utf-8")
    chrome = sys.argv[1] if len(sys.argv) > 1 else shutil.which("chromium") or shutil.which("google-chrome")
    if chrome:
        subprocess.run([chrome, "--headless", "--no-sandbox", "--disable-gpu", "--hide-scrollbars",
                        "--window-size=1280,640", f"--screenshot={ROOT / 'assets' / 'social-preview.png'}",
                        page.as_uri()], check=True, capture_output=True)
        print("wrote assets/social-preview.png")
    else:
        print("wrote assets/social-preview.html (no Chromium found to render the PNG)")


if __name__ == "__main__":
    main()
