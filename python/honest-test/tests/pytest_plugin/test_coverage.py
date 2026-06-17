"""Pure tests for _coverage.py."""
from pathlib import Path

from honest_test.pytest_plugin._coverage import (
    DEFAULT_EXCLUDED_DIR_NAMES,
    compute_coverage,
    discover_source_files,
    find_public_functions,
    function_has_assert,
    has_excluded_dir_part,
    is_excluded,
    names_referenced,
    render_coverage_report,
)


# --- find_public_functions -----------------------------------------------


def test_find_public_functions_skip_private_by_default():
    src = (
        "def alpha(): pass\n"
        "def _beta(): pass\n"
        "def gamma(): pass\n"
    )
    assert find_public_functions(src) == ["alpha", "gamma"]


def test_find_public_functions_include_private():
    src = "def alpha(): pass\ndef _beta(): pass\n"
    assert find_public_functions(src, private_functions="include") == [
        "alpha", "_beta",
    ]


def test_find_public_functions_ignores_nested():
    src = (
        "def alpha():\n"
        "    def inner(): pass\n"
        "    return inner\n"
    )
    assert find_public_functions(src) == ["alpha"]


def test_find_public_functions_handles_async():
    src = "async def alpha(): pass\ndef beta(): pass\n"
    assert find_public_functions(src) == ["alpha", "beta"]


# --- names_referenced -----------------------------------------------------


def test_names_referenced_unqualified_call():
    src = "def test_x():\n    add(1, 2)\n"
    names = names_referenced(src)
    assert "add" in names


def test_names_referenced_attribute_access():
    src = "import lib\ndef test_x():\n    lib.add(1, 2)\n"
    names = names_referenced(src)
    assert "add" in names
    assert "lib" in names


def test_names_referenced_import_from_alias():
    src = "from lib import add as plus\ndef test_x():\n    plus(1, 2)\n"
    names = names_referenced(src)
    assert "plus" in names


# --- function_has_assert --------------------------------------------------


def test_function_has_assert_true():
    src = "def test_x():\n    assert 1 == 1\n"
    assert function_has_assert(src, "test_x")


def test_function_has_assert_false_when_no_assert():
    src = "def test_x():\n    pass\n"
    assert not function_has_assert(src, "test_x")


def test_function_has_assert_finds_nested_assert():
    src = (
        "def test_x():\n"
        "    for i in range(3):\n"
        "        assert i < 3\n"
    )
    assert function_has_assert(src, "test_x")


def test_function_has_assert_returns_false_when_missing():
    src = "def test_x():\n    assert 1\n"
    assert not function_has_assert(src, "test_y")


# --- is_excluded ----------------------------------------------------------


def test_is_excluded_substring_match():
    assert is_excluded("apps/routes/foo.py", ["routes/"])


def test_is_excluded_no_match():
    assert not is_excluded("apps/services/foo.py", ["routes/"])


# --- has_excluded_dir_part -----------------------------------------------


def test_has_excluded_dir_part_catches_venv():
    p = Path("/proj/apps/.venv/lib/python3.12/site-packages/foo/bar.py")
    assert has_excluded_dir_part(p, DEFAULT_EXCLUDED_DIR_NAMES)


def test_has_excluded_dir_part_catches_pycache():
    p = Path("/proj/apps/services/__pycache__/foo.cpython-312.pyc.py")
    assert has_excluded_dir_part(p, DEFAULT_EXCLUDED_DIR_NAMES)


def test_has_excluded_dir_part_catches_node_modules():
    p = Path("/proj/apps/node_modules/somepkg/x.py")
    assert has_excluded_dir_part(p, DEFAULT_EXCLUDED_DIR_NAMES)


def test_has_excluded_dir_part_ignores_clean_path():
    p = Path("/proj/apps/services/foo.py")
    assert not has_excluded_dir_part(p, DEFAULT_EXCLUDED_DIR_NAMES)


def test_default_excluded_dir_names_covers_common_cases():
    # Smoke check on the canonical set; if these ever drop out we want
    # the test to fail loudly.
    for name in [".venv", "__pycache__", ".pytest_cache", "node_modules"]:
        assert name in DEFAULT_EXCLUDED_DIR_NAMES


# --- discover_source_files (real filesystem, no mocks) ------------------


def test_discover_source_files_skips_venv(tmp_path: Path):
    apps = tmp_path / "apps"
    apps.mkdir()
    (apps / "real.py").write_text("def f(): pass\n")
    venv_pkg = apps / ".venv" / "lib" / "site-packages" / "noisepkg"
    venv_pkg.mkdir(parents=True)
    (venv_pkg / "bogus.py").write_text("def g(): pass\n")
    (venv_pkg / "more.py").write_text("def h(): pass\n")

    found = discover_source_files(["apps"], [], tmp_path)

    assert len(found) == 1
    assert any(p.endswith("real.py") for p in found)
    assert not any(".venv" in p for p in found)


def test_discover_source_files_skips_pycache(tmp_path: Path):
    apps = tmp_path / "apps"
    apps.mkdir()
    (apps / "real.py").write_text("def f(): pass\n")
    cache = apps / "__pycache__"
    cache.mkdir()
    (cache / "fake.py").write_text("def g(): pass\n")

    found = discover_source_files(["apps"], [], tmp_path)

    assert len(found) == 1
    assert not any("__pycache__" in p for p in found)


def test_discover_source_files_user_excludes_still_apply(tmp_path: Path):
    apps = tmp_path / "apps"
    routes = apps / "routes"
    services = apps / "services"
    routes.mkdir(parents=True)
    services.mkdir(parents=True)
    (routes / "r.py").write_text("def r(): pass\n")
    (services / "s.py").write_text("def s(): pass\n")

    found = discover_source_files(["apps"], ["routes/"], tmp_path)

    assert len(found) == 1
    assert any(p.endswith("s.py") for p in found)


# --- compute_coverage end-to-end -----------------------------------------


def test_compute_coverage_pins_referenced_function():
    source_files = {
        "apps/math.py": "def add(a, b): return a + b\ndef sub(a, b): return a - b\n",
    }
    test_modules = {
        "tests/test_math.py": (
            "from apps.math import add\n"
            "def test_add():\n"
            "    assert add(1, 2) == 3\n"
        ),
    }
    asserting_items = [("tests/test_math.py", "test_add")]
    report = compute_coverage(source_files, test_modules, asserting_items)
    assert report["total_functions"] == 2
    assert report["total_pinned"] == 1  # add pinned, sub not
    row = report["rows"][0]
    assert dict(row["function_names"]) == {"add": True, "sub": False}


def test_compute_coverage_unpins_when_no_assert():
    source_files = {"apps/math.py": "def add(a, b): return a + b\n"}
    test_modules = {
        "tests/test_math.py": (
            "from apps.math import add\n"
            "def test_add():\n"
            "    add(1, 2)\n"  # called but not asserted
        ),
    }
    asserting_items: list[tuple[str, str]] = []
    report = compute_coverage(source_files, test_modules, asserting_items)
    assert report["total_pinned"] == 0


def test_compute_coverage_empty_inputs():
    report = compute_coverage({}, {}, [])
    assert report["rows"] == []
    assert report["total_pinned"] == 0
    assert report["total_functions"] == 0


def test_compute_coverage_multiple_files():
    source_files = {
        "apps/a.py": "def alpha(): pass\n",
        "apps/b.py": "def beta(): pass\n",
    }
    test_modules = {
        "tests/test_a.py": (
            "from apps.a import alpha\n"
            "def test_alpha():\n"
            "    alpha()\n"
            "    assert True\n"
        ),
    }
    asserting_items = [("tests/test_a.py", "test_alpha")]
    report = compute_coverage(source_files, test_modules, asserting_items)
    assert report["total_functions"] == 2
    assert report["total_pinned"] == 1


# --- render_coverage_report ----------------------------------------------


def test_render_coverage_report_basic():
    report = {
        "rows": [{
            "file": "apps/math.py",
            "pinned": 1,
            "total": 2,
            "function_names": [("add", True), ("sub", False)],
        }],
        "total_pinned": 1,
        "total_functions": 2,
    }
    out = render_coverage_report(report)
    assert "honest contract coverage" in out
    assert "apps/" in out
    assert "math.py" in out
    assert "1 pinned" in out
    assert "Total: 1 pinned / 2 functions" in out


def test_render_coverage_report_zero_functions_safe():
    report = {"rows": [], "total_pinned": 0, "total_functions": 0}
    out = render_coverage_report(report)
    # No divide-by-zero crash; report still renders
    assert "honest contract coverage" in out
    assert "Total: 0 pinned / 0 functions" in out
