"""Unit 4: honest-check.toml config + github/junit output formats."""
from honest_check import check_source
from honest_check.cli import _apply_config, render_github, render_junit
from honest_check.config import is_excluded, meets_severity, normalize_config


def test_normalize_config():
    raw = {"check": {"paths": ["src/"], "exclude": ["**/migrations/"], "severity": "error"},
           "rules": {"disable": ["HC-P006"]}}
    cfg = normalize_config(raw)
    assert cfg == {"paths": ["src/"], "exclude": ["**/migrations/"],
                   "severity": "error", "disable": ["HC-P006"]}


def test_normalize_config_defaults():
    cfg = normalize_config({})
    assert cfg["severity"] == "warning" and cfg["disable"] == []


def test_meets_severity():
    assert meets_severity("error", "warning")
    assert not meets_severity("warning", "error")
    assert meets_severity("warning", "warning")


def test_is_excluded():
    assert is_excluded("src/migrations/0001.py", ["**/migrations/*"])
    assert not is_excluded("src/app.py", ["**/migrations/*"])


def _report(src):
    return [("x.py", check_source(src, "x.py"))]


def test_render_github():
    out = render_github(_report("class Foo:\n    pass\n"))
    assert "::error" in out and "title=HC-P003" in out and "file=x.py" in out


def test_render_junit():
    out = render_junit(_report("class Foo:\n    pass\n"))
    assert "<testsuites" in out and "HC-P003" in out and "<failure" in out


def test_apply_config_disables_rule():
    report = check_source("class Foo:\n    pass\n", "x.py")
    filtered = _apply_config(report, ["HC-P003"], "info")
    assert filtered["total_errors"] == 0


def test_apply_config_severity_threshold_drops_warnings():
    # isinstance -> HC-P005 warning; threshold "error" should drop it.
    report = check_source("def f(x):\n    return isinstance(x, str)\n", "x.py")
    filtered = _apply_config(report, [], "error")
    assert all(d["severity"] == "error" for d in filtered["diagnostics"])
