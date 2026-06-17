"""Pure tests for _lint.py. No mocks — we feed source strings directly
to `find_violations` and assert on the returned violation list.
"""
from honest_test.pytest_plugin._lint import find_violations, is_exempt


def violations_of(source: str, source_roots=None) -> list[str]:
    """Helper: return list of `reason` strings for a source snippet."""
    roots = source_roots if source_roots is not None else []
    return [v["reason"] for v in find_violations(source, "x.py", roots)]


# --- imports --------------------------------------------------------------


def test_flags_from_unittest_mock_import():
    reasons = violations_of("from unittest.mock import MagicMock\n")
    assert any("unittest.mock" in r for r in reasons)


def test_flags_from_unittest_import_mock():
    reasons = violations_of("from unittest import mock\n")
    assert any("unittest.mock" in r for r in reasons)


def test_flags_import_unittest_mock():
    reasons = violations_of("import unittest.mock\n")
    assert any("unittest.mock" in r for r in reasons)


def test_flags_pytest_mock_import():
    reasons = violations_of("from pytest_mock import MockerFixture\n")
    assert any("pytest_mock" in r for r in reasons)


def test_ignores_plain_unittest_import():
    assert violations_of("import unittest\n") == []


# --- mock constructors ----------------------------------------------------


def test_flags_magicmock_call():
    reasons = violations_of("from unittest.mock import MagicMock\nx = MagicMock()\n")
    assert any("MagicMock" in r for r in reasons)


def test_flags_attr_mock_call():
    reasons = violations_of("import unittest.mock\nx = unittest.mock.Mock()\n")
    assert any("Mock" in r for r in reasons)


def test_flags_asyncmock_call():
    reasons = violations_of("from unittest.mock import AsyncMock\nx = AsyncMock()\n")
    assert any("AsyncMock" in r for r in reasons)


# --- @patch decorator family ----------------------------------------------


def test_flags_patch_decorator():
    src = (
        "from unittest.mock import patch\n"
        "@patch('x.y')\n"
        "def test_x(p): pass\n"
    )
    reasons = violations_of(src)
    assert any("patch" in r for r in reasons)


def test_flags_patch_object_decorator():
    src = (
        "from unittest.mock import patch\n"
        "@patch.object(SomeClass, 'method')\n"
        "def test_x(p): pass\n"
    )
    reasons = violations_of(src)
    assert any("patch" in r for r in reasons)


def test_flags_mock_patch_attr_decorator():
    src = (
        "from unittest import mock\n"
        "@mock.patch('x.y')\n"
        "def test_x(p): pass\n"
    )
    reasons = violations_of(src)
    assert any("patch" in r for r in reasons)


# --- monkeypatch.setattr boundary ----------------------------------------


def test_flags_monkeypatch_setattr_string_targeting_source_root():
    src = (
        "def test_x(monkeypatch):\n"
        "    monkeypatch.setattr('apps.x.y', 7)\n"
    )
    reasons = violations_of(src, source_roots=["apps"])
    assert any("apps.x.y" in r for r in reasons)


def test_flags_monkeypatch_setattr_attribute_targeting_source_root():
    src = (
        "import apps.x\n"
        "def test_x(monkeypatch):\n"
        "    monkeypatch.setattr(apps.x, 'y', 7)\n"
    )
    reasons = violations_of(src, source_roots=["apps"])
    # attribute form resolves to "apps.x" — should match
    assert any("apps.x" in r for r in reasons)


def test_ignores_monkeypatch_setattr_outside_source_roots():
    src = (
        "def test_x(monkeypatch):\n"
        "    monkeypatch.setattr('os.environ', {})\n"
    )
    # source_roots = ["apps"], target is os.environ, no match
    assert violations_of(src, source_roots=["apps"]) == []


def test_ignores_monkeypatch_setattr_when_no_source_roots():
    src = (
        "def test_x(monkeypatch):\n"
        "    monkeypatch.setattr('apps.x.y', 7)\n"
    )
    # Empty source_roots = adoption-friendly: don't reject
    assert violations_of(src, source_roots=[]) == []


# --- false-positive boundary ---------------------------------------------


def test_does_not_flag_tmp_path_fixture():
    src = (
        "def test_x(tmp_path):\n"
        "    (tmp_path / 'a').write_text('hi')\n"
    )
    assert violations_of(src) == []


def test_does_not_flag_simplenamespace():
    src = (
        "from types import SimpleNamespace\n"
        "def test_x():\n"
        "    s = SimpleNamespace(a=1)\n"
        "    assert s.a == 1\n"
    )
    assert violations_of(src) == []


def test_does_not_flag_attribute_snapshot_restore():
    src = (
        "import apps.x\n"
        "def test_x():\n"
        "    saved = apps.x.Y\n"
        "    apps.x.Y = 42\n"
        "    try:\n"
        "        assert apps.x.Y == 42\n"
        "    finally:\n"
        "        apps.x.Y = saved\n"
    )
    # No monkeypatch.setattr, no mock symbols. Honest substitution.
    assert violations_of(src, source_roots=["apps"]) == []


# --- exemption helper -----------------------------------------------------


def test_is_exempt_matches_glob():
    assert is_exempt("tests/legacy/foo.py", ["tests/legacy/*.py"])


def test_is_exempt_no_match():
    assert not is_exempt("tests/unit/foo.py", ["tests/legacy/*.py"])


def test_is_exempt_empty_patterns():
    assert not is_exempt("tests/foo.py", [])


# --- violation record shape ----------------------------------------------


def test_violation_carries_path_and_line():
    source = (
        "x = 1\n"
        "from unittest.mock import MagicMock\n"
        "y = 2\n"
    )
    violations = find_violations(source, "tests/foo.py", [])
    assert violations[0]["path"] == "tests/foo.py"
    assert violations[0]["line"] == 2
