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
