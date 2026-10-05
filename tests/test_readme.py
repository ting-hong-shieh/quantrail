"""The README quickstart must keep running exactly as written."""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("name", ["README.md", "README.zh-TW.md"])
def test_quickstart_runs_and_reports_the_documented_flags(name, capsys):
    text = (ROOT / name).read_text(encoding="utf-8")
    code = re.findall(r"```python\n(.*?)```", text, flags=re.S)[0]
    exec(compile(code, name, "exec"), {})
    output = capsys.readouterr().out
    documented = re.findall(r"\[[!i]\] ([A-Z_]+):", text)
    assert documented, "README should show the expected trust report"
    for code_name in documented:
        assert code_name in output


@pytest.mark.parametrize("name", ["README.md", "README.zh-TW.md"])
def test_links_and_images_are_absolute_so_pypi_can_render_them(name):
    """PyPI shows the README without the repository, so relative paths break there."""
    text = (ROOT / name).read_text(encoding="utf-8")
    html_refs = re.findall(r'(?:src|href)="([^"]+)"', text)
    md_refs = re.findall(r"\]\(([^)\s]+)\)", text)
    relative = [r for r in html_refs + md_refs if not re.match(r"^(https?:|#|mailto:)", r)]
    assert relative == [], f"relative links in {name}: {relative}"
