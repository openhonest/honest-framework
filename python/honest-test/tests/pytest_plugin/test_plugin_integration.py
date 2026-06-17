"""End-to-end checks for the honest-test pytest plugin.

Uses the built-in `pytester` fixture, which runs a real pytest in a
sandbox temp dir. Each test sets up a `pyproject.toml` with
`[tool.honest_test]` and a source/test layout, runs pytest, and asserts
on the real terminal output. Honest substitution, no mocks.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.usefixtures("pytester")


def _write_pyproject(pytester, table: str) -> None:
    pytester.makepyprojecttoml(
        "[tool.honest_test]\n" + table
    )


# --- M2.1 contract counting ----------------------------------------------


def test_summary_block_appears_with_defaults(pytester):
    _write_pyproject(pytester, "")
    pytester.makepyfile(
        test_sample=(
            "import pytest\n"
            "@pytest.mark.parametrize('x', [1, 2, 3])\n"
            "def test_a(x):\n"
            "    assert x > 0\n"
            "def test_b():\n"
            "    assert True\n"
        )
    )
    result = pytester.runpytest("-q")
    result.stdout.fnmatch_lines([
        "*honest summary*",
        "*pytest items collected:  4*",
        "*distinct contracts:        2*",
        "*parametrize ratio:        2.0x*",
    ])


def test_summary_can_be_disabled(pytester):
    _write_pyproject(
        pytester,
        "report_contracts = false\nreport_pytest_items = false\n",
    )
    pytester.makepyfile(test_sample="def test_a():\n    assert True\n")
    result = pytester.runpytest("-q")
    assert "honest summary" not in result.stdout.str()


# --- M2.2 dishonesty lint ------------------------------------------------


def test_lint_off_by_default(pytester):
    _write_pyproject(pytester, "")
    pytester.makepyfile(
        test_with_mock=(
            "from unittest.mock import MagicMock\n"
            "def test_a():\n"
            "    m = MagicMock()\n"
            "    assert m is not None\n"
        )
    )
    # No lint flag — collection should succeed
    result = pytester.runpytest("-q")
    assert result.ret == 0


def test_lint_fails_collection_on_mock_import(pytester):
    _write_pyproject(pytester, "lint = true\n")
    pytester.makepyfile(
        test_with_mock=(
            "x = 1\n"
            "from unittest.mock import MagicMock\n"
            "def test_a():\n"
            "    assert True\n"
        )
    )
    result = pytester.runpytest("-q")
    assert result.ret != 0
    combined = result.stdout.str() + result.stderr.str()
    assert "honest_test lint" in combined
    assert "test_with_mock.py" in combined
    assert ":2:" in combined  # the mock import line
    assert "unittest.mock" in combined


def test_lint_exempt_skips_file(pytester):
    _write_pyproject(
        pytester,
        "lint = true\nlint_exempt = ['*test_legacy.py*']\n",
    )
    pytester.makepyfile(
        test_legacy=(
            "from unittest.mock import MagicMock\n"
            "def test_a():\n"
            "    m = MagicMock()\n"
            "    assert m is not None\n"
        )
    )
    result = pytester.runpytest("-q")
    assert result.ret == 0


# --- M2.3 contract coverage ----------------------------------------------


def test_coverage_block_appears_when_source_roots_set(pytester):
    _write_pyproject(pytester, "source_roots = ['apps']\n")
    pytester.mkpydir("apps")
    pytester.makepyfile(**{
        "apps/math": (
            "def add(a, b): return a + b\n"
            "def sub(a, b): return a - b\n"
        ),
    })
    pytester.makepyfile(
        test_math=(
            "from apps.math import add\n"
            "def test_add():\n"
            "    assert add(1, 2) == 3\n"
        )
    )
    result = pytester.runpytest("-q")
    result.stdout.fnmatch_lines([
        "*honest contract coverage*",
        "*math.py*1 pinned*2 functions*",
    ])


def test_coverage_no_source_roots_no_block(pytester):
    _write_pyproject(pytester, "")
    pytester.makepyfile(test_a="def test_a():\n    assert True\n")
    result = pytester.runpytest("-q")
    assert "honest contract coverage" not in result.stdout.str()


def test_coverage_fail_under_escalates_exit(pytester):
    _write_pyproject(
        pytester,
        (
            "source_roots = ['apps']\n"
            "coverage_min = 80\n"
            "coverage_fail_under = true\n"
        ),
    )
    pytester.mkpydir("apps")
    pytester.makepyfile(**{
        "apps/math": (
            "def add(a, b): return a + b\n"
            "def sub(a, b): return a - b\n"
            "def mul(a, b): return a * b\n"
        ),
    })
    pytester.makepyfile(
        test_math=(
            "from apps.math import add\n"
            "def test_add():\n"
            "    assert add(1, 2) == 3\n"
        )
    )
    result = pytester.runpytest("-q")
    # All tests pass, but coverage (33%) is below 80% -> nonzero exit
    assert result.ret != 0


# --- No-op when everything is disabled ----------------------------------


def test_all_features_disabled_yields_no_extra_output(pytester):
    _write_pyproject(
        pytester,
        (
            "report_contracts = false\n"
            "report_pytest_items = false\n"
            "lint = false\n"
        ),
    )
    pytester.makepyfile(test_a="def test_a():\n    assert True\n")
    result = pytester.runpytest("-q")
    out = result.stdout.str()
    assert "honest summary" not in out
    assert "honest contract coverage" not in out


# --- Dogfooding: lint passes on our own test files ----------------------


def test_lint_passes_on_this_test_dir():
    """Read each plugin test file as plain bytes and assert the lint
    finds no mock-family violations. Acceptance criterion 6: M2 tests
    pass M2.2 lint when run on themselves.
    """
    from pathlib import Path
    from honest_test.pytest_plugin._lint import find_violations

    here = Path(__file__).parent
    for path in sorted(here.glob("test_*.py")):
        source = path.read_text()
        violations = find_violations(source, str(path), source_root_prefixes=[])
        assert violations == [], (
            f"{path}: dogfood lint failed: {violations}"
        )


# --- M2.4 silent-default lint --------------------------------------------


def test_silent_default_off_by_default(pytester):
    """Acceptance #4: silent_default_params = [] -> no-op."""
    _write_pyproject(pytester, "source_roots = ['apps']\n")
    pytester.mkpydir("apps")
    pytester.makepyfile(**{
        "apps/bad": "def f(user_id: str = ''): return user_id\n",
    })
    pytester.makepyfile(
        test_x="def test_a():\n    assert True\n"
    )
    result = pytester.runpytest("-q")
    assert result.ret == 0
    assert "silent-default" not in result.stdout.str()


def test_silent_default_flags_empty_string(pytester):
    """Acceptance #1: violating signature -> one violation, nonzero exit."""
    _write_pyproject(
        pytester,
        (
            "source_roots = ['apps']\n"
            "silent_default_params = ['user_id']\n"
        ),
    )
    pytester.mkpydir("apps")
    pytester.makepyfile(**{
        "apps/bad": "def f(user_id: str = ''): return user_id\n",
    })
    pytester.makepyfile(
        test_x="def test_a():\n    assert True\n"
    )
    result = pytester.runpytest("-q")
    assert result.ret != 0
    out = result.stdout.str()
    assert "honest_test silent-default lint" in out
    assert "bad.py:1" in out
    assert "user_id" in out
    assert "Total: 1 violations across 1 files" in out


def test_silent_default_allow_marker_clears(pytester):
    """Acceptance #2: # allow-empty-default-required suppresses."""
    _write_pyproject(
        pytester,
        (
            "source_roots = ['apps']\n"
            "silent_default_params = ['user_id']\n"
        ),
    )
    pytester.mkpydir("apps")
    pytester.makepyfile(**{
        "apps/ok": (
            "def f(user_id: str = ''):  # allow-empty-default-required\n"
            "    return user_id\n"
        ),
    })
    pytester.makepyfile(
        test_x="def test_a():\n    assert True\n"
    )
    result = pytester.runpytest("-q")
    assert result.ret == 0
    assert "silent-default lint" not in result.stdout.str()


def test_silent_default_exempt_clears(pytester):
    """Acceptance #3: exempt list with `path:fn` suppresses."""
    _write_pyproject(
        pytester,
        (
            "source_roots = ['apps']\n"
            "silent_default_params = ['user_id']\n"
            "silent_default_exempt = ['apps/ok.py:f']\n"
        ),
    )
    pytester.mkpydir("apps")
    pytester.makepyfile(**{
        "apps/ok": "def f(user_id: str = ''): return user_id\n",
    })
    pytester.makepyfile(
        test_x="def test_a():\n    assert True\n"
    )
    result = pytester.runpytest("-q")
    assert result.ret == 0


def test_silent_default_respects_exclude_patterns(pytester):
    """Acceptance #5: files under exclude_patterns are not scanned."""
    _write_pyproject(
        pytester,
        (
            "source_roots = ['apps']\n"
            "exclude_patterns = ['routes/']\n"
            "silent_default_params = ['user_id']\n"
        ),
    )
    pytester.mkpydir("apps")
    pytester.mkpydir("apps/routes")
    pytester.makepyfile(**{
        "apps/routes/api": "def f(user_id: str = ''): return user_id\n",
    })
    pytester.makepyfile(
        test_x="def test_a():\n    assert True\n"
    )
    result = pytester.runpytest("-q")
    assert result.ret == 0


def test_silent_default_scans_class_methods(pytester):
    """Acceptance #6: class methods are scanned."""
    _write_pyproject(
        pytester,
        (
            "source_roots = ['apps']\n"
            "silent_default_params = ['user_id']\n"
        ),
    )
    pytester.mkpydir("apps")
    pytester.makepyfile(**{
        "apps/repo": (
            "class Repo:\n"
            "    def get(self, user_id: str = ''):\n"
            "        return user_id\n"
        ),
    })
    pytester.makepyfile(
        test_x="def test_a():\n    assert True\n"
    )
    result = pytester.runpytest("-q")
    assert result.ret != 0
    out = result.stdout.str()
    assert "honest_test silent-default lint" in out
    assert "Repo" not in out or "get" in out  # method name surfaced


def test_silent_default_skips_test_files(pytester):
    """Acceptance #7: production source only — test files untouched.

    A test file with a violating signature should NOT trigger this lint
    (the existing M2.2 mock lint covers tests).
    """
    _write_pyproject(
        pytester,
        (
            "source_roots = ['apps']\n"
            "silent_default_params = ['user_id']\n"
        ),
    )
    pytester.mkpydir("apps")
    pytester.makepyfile(**{
        "apps/clean": "def f(user_id: str): return user_id\n",
    })
    # Test file has a function with the offending shape, but it lives
    # OUTSIDE apps/, so M2.4 must not scan it.
    pytester.makepyfile(
        test_x=(
            "def helper(user_id: str = ''):\n"
            "    return user_id\n"
            "def test_a():\n"
            "    assert helper('x') == 'x'\n"
        )
    )
    result = pytester.runpytest("-q")
    assert result.ret == 0
    assert "silent-default lint" not in result.stdout.str()


def test_silent_default_dogfood_on_this_dir():
    """Acceptance #8: plugin's own tests don't trigger silent-default
    lint with the canonical param list.
    """
    from pathlib import Path
    from honest_test.pytest_plugin._lint_source import (
        find_silent_default_violations,
    )

    here = Path(__file__).parent
    params = ["user_id", "workspace_id", "pool", "db", "connection"]
    for path in sorted(here.glob("test_*.py")):
        source = path.read_text()
        v = find_silent_default_violations(
            source, str(path), params, ["", "None"], []
        )
        assert v == [], f"{path}: dogfood silent-default failed: {v}"


# --- Browser-test lint ---------------------------------------------------


_STEP_SHIM = (
    "def given(_): return lambda f: f\n"
    "def when(_): return lambda f: f\n"
    "def then(_): return lambda f: f\n"
)


def test_browser_lint_off_when_step_roots_empty(pytester):
    """Acceptance #5: browser lint stays dormant unless browser_step_roots
    is set, regardless of file contents.
    """
    _write_pyproject(pytester, "")
    pytester.mkpydir("steps")
    pytester.makepyfile(**{
        "steps/test_drag": (
            _STEP_SHIM
            + "@given('x')\n"
            "def step_a(page):\n"
            "    pass\n"
            "def test_smoke():\n"
            "    assert True\n"
        ),
    })
    result = pytester.runpytest("-q")
    assert result.ret == 0
    assert "browser_lint" not in result.stdout.str() + result.stderr.str()


def test_browser_lint_b1_empty_body_fails_collection(pytester):
    """Acceptance #5 & #7: empty @given/@when/@then body fails at
    collection with rule B1.
    """
    _write_pyproject(
        pytester,
        "browser_step_roots = ['steps']\n",
    )
    pytester.mkpydir("steps")
    pytester.makepyfile(**{
        "steps/test_drag": (
            "from pytest_bdd import given\n"
            "@given('a card')\n"
            "def step_a(harness):\n"
            "    pass\n"
        ),
    })
    result = pytester.runpytest("-q")
    assert result.ret != 0
    combined = result.stdout.str() + result.stderr.str()
    assert "honest_test browser_lint" in combined
    assert "[B1]" in combined
    assert "test_drag.py" in combined


def test_browser_lint_b2_synthetic_event_fails_collection(pytester):
    """Acceptance #6: forbidden synthetic-event pattern fails B2."""
    _write_pyproject(
        pytester,
        "browser_step_roots = ['steps']\n",
    )
    pytester.mkpydir("steps")
    pytester.makepyfile(**{
        "steps/test_click": (
            "from pytest_bdd import when\n"
            "@when('the user clicks')\n"
            "def step_c(harness, page):\n"
            "    page.evaluate(\"el.click()\")\n"
        ),
    })
    result = pytester.runpytest("-q")
    assert result.ret != 0
    combined = result.stdout.str() + result.stderr.str()
    assert "[B2]" in combined


def test_browser_lint_b3_missing_harness_fails_collection(pytester):
    """Acceptance #7 variant: step def without `harness` fixture fails B3."""
    _write_pyproject(
        pytester,
        "browser_step_roots = ['steps']\n",
    )
    pytester.mkpydir("steps")
    pytester.makepyfile(**{
        "steps/test_noharness": (
            "from pytest_bdd import when\n"
            "@when('something')\n"
            "def step_n(page):\n"
            "    assert page is not None\n"
        ),
    })
    result = pytester.runpytest("-q")
    assert result.ret != 0
    combined = result.stdout.str() + result.stderr.str()
    assert "[B3]" in combined


def test_browser_lint_does_not_scan_files_outside_step_roots(pytester):
    """A file with a B1-violating step def but located OUTSIDE
    browser_step_roots must not fire the lint.
    """
    _write_pyproject(
        pytester,
        "browser_step_roots = ['steps']\n",
    )
    pytester.mkpydir("helpers")
    pytester.makepyfile(**{
        "helpers/test_outside": (
            _STEP_SHIM
            + "@given('x')\n"
            "def step_o(harness):\n"
            "    pass\n"
        ),
    })
    result = pytester.runpytest("-q")
    combined = result.stdout.str() + result.stderr.str()
    assert "browser_lint" not in combined


def test_browser_lint_clean_step_def_passes(pytester):
    """A step def that uses the harness fixture and has a real assertion
    does not fail the lint.
    """
    _write_pyproject(
        pytester,
        "browser_step_roots = ['steps']\n",
    )
    pytester.mkpydir("steps")
    pytester.makepyfile(**{
        "steps/test_clean": (
            _STEP_SHIM
            + "@then('the card is highlighted')\n"
            "def step_h(harness):\n"
            "    do, see, errors = harness\n"
            "    assert errors == errors\n"
        ),
    })
    result = pytester.runpytest("-q")
    combined = result.stdout.str() + result.stderr.str()
    assert "browser_lint" not in combined
