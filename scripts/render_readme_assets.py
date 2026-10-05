"""Regenerate README images from real output: python scripts/render_readme_assets.py

assets/trust-report.svg is drawn from the actual report printed by the README
quickstart, so the picture can never claim something the code does not do.
"""

from __future__ import annotations

import contextlib
import io
import re
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COLORS = {"!": "#F59E0B", "i": "#38BDF8", "x": "#F87171"}
MONO = "ui-monospace, SFMono-Regular, Menlo, Consolas, 'DejaVu Sans Mono', monospace"


def quickstart_output() -> str:
    code = re.findall(r"```python\n(.*?)```", (ROOT / "README.md").read_text(encoding="utf-8"), flags=re.S)[0]
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        exec(compile(code, "README.md", "exec"), {})
    return buffer.getvalue().rstrip("\n")


def terminal_svg(text: str, *, title: str = "python quickstart.py") -> str:
    lines = text.splitlines()
    char_w, line_h, pad, top = 7.8, 21, 22, 48
    width = int(max(len(line) for line in lines) * char_w + 2 * pad)
    height = top + len(lines) * line_h + pad
    rows = []
    for i, line in enumerate(lines):
        y = top + (i + 1) * line_h - 6
        match = re.match(r"^(\s*)\[([!ix])\] ([A-Z_]+)(:.*)$", line)
        if match:
            indent, mark, code, rest = match.groups()
            rows.append(
                f'<text x="{pad}" y="{y}" xml:space="preserve">{escape(indent)}'
                f'<tspan fill="{COLORS[mark]}">[{mark}]</tspan> '
                f'<tspan fill="#F8FAFC" font-weight="700">{escape(code)}</tspan>'
                f'<tspan fill="#94A3B8">{escape(rest)}</tspan></text>')
        else:
            color = "#5EEAD4" if line.endswith(":") and not line.startswith(" ") else "#CBD5E1"
            rows.append(f'<text x="{pad}" y="{y}" fill="{color}" xml:space="preserve">{escape(line)}</text>')
    size = f'width="{width}" height="{height}" viewBox="0 0 {width} {height}"'
    return f'''<svg xmlns="http://www.w3.org/2000/svg" {size}
     role="img" aria-label="QuantRail trust report printed by the README quickstart">
  <rect width="{width}" height="{height}" rx="12" fill="#0F172A"/>
  <circle cx="22" cy="20" r="6" fill="#F87171"/><circle cx="42" cy="20" r="6" fill="#FBBF24"/>
  <circle cx="62" cy="20" r="6" fill="#34D399"/>
  <text x="{width / 2}" y="25" fill="#64748B" text-anchor="middle"
        font-family="{MONO}" font-size="12">{escape(title)}</text>
  <g font-family="{MONO}" font-size="13">
    {chr(10).join("    " + row for row in rows).strip()}
  </g>
</svg>
'''


def main() -> None:
    (ROOT / "assets").mkdir(exist_ok=True)
    (ROOT / "assets" / "trust-report.svg").write_text(terminal_svg(quickstart_output()), encoding="utf-8")
    print("wrote assets/trust-report.svg")


if __name__ == "__main__":
    main()
