"""Pure tests for _config.py — no mocks. We test `merge_config` directly
with literal dicts. `load_honest_test_config` is exercised by writing
a real pyproject.toml to tmp_path (real filesystem, honest substitution).
"""
from pathlib import Path

from honest_test.pytest_plugin._config import (
    DEFAULTS,
    load_honest_test_config,
    merge_config,
)


def test_merge_config_empty_raw_returns_defaults():
    merged = merge_config({})
    assert merged == DEFAULTS


def test_merge_config_overrides_lint():
    merged = merge_config({"lint": True})
    assert merged["lint"] is True
    assert merged["report_contracts"] is True  # default preserved


def test_merge_config_ignores_unknown_keys():
    merged = merge_config({"bogus": "x", "lint": True})
    assert "bogus" not in merged
    assert merged["lint"] is True


def test_merge_config_overrides_lists():
    merged = merge_config({
        "source_roots": ["apps", "lib"],
        "exclude_patterns": ["routes/"],
    })
    assert merged["source_roots"] == ["apps", "lib"]
    assert merged["exclude_patterns"] == ["routes/"]


def test_load_honest_test_config_missing_pyproject(tmp_path: Path):
    htc = load_honest_test_config(tmp_path)
    assert htc == DEFAULTS


def test_load_honest_test_config_reads_table(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text(
        "[tool.honest_test]\n"
        "lint = true\n"
        'source_roots = ["apps"]\n'
        "coverage_min = 80\n"
    )
    htc = load_honest_test_config(tmp_path)
    assert htc["lint"] is True
    assert htc["source_roots"] == ["apps"]
    assert htc["coverage_min"] == 80
    assert htc["report_contracts"] is True


def test_load_honest_test_config_missing_table(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'x'\n")
    htc = load_honest_test_config(tmp_path)
    assert htc == DEFAULTS
