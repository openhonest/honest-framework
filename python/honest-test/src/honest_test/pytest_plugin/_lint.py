"""M2.2 dishonesty lint. Pure AST scanner that returns a list of
LintViolation TypedDicts. The pytest hook calls `find_violations` and
fails the session on non-empty result.

Detection vocabulary (set, not chain):
  - mock-family imports:    unittest.mock, mock, pytest_mock
  - mock-family constructors: MagicMock, Mock, AsyncMock
  - mock.patch decorator family
  - monkeypatch.setattr with a target inside a configured source root

False-positive boundary: tmp_path, types.SimpleNamespace, and direct
attribute snapshot/restore (saved=mod.X; mod.X=...; mod.X=saved) are
intentionally NOT detected. See SPEC-M2.md §M2.2.
"""
from __future__ import annotations

import ast
import fnmatch
from pathlib import Path

from honest_test.pytest_plugin._types import LintViolation


MOCK_MODULES = frozenset({"unittest.mock", "mock", "pytest_mock"})
MOCK_CTORS = frozenset({"MagicMock", "Mock", "AsyncMock"})


def is_exempt(path: str, patterns: list[str]) -> bool:
    """Pure: does `path` match any glob in `patterns`?"""
    return any(fnmatch.fnmatch(path, pat) for pat in patterns)


def find_violations(
    source: str,
    path: str,
    source_root_prefixes: list[str],
) -> list[LintViolation]:
    """Pure: AST-walk `source` and return every mock-family violation.

    `path` is threaded through unchanged for the violation record;
    `source_root_prefixes` decides whether a monkeypatch.setattr
    string target counts as production-module rejection.
    """
    tree = ast.parse(source)
    violations: list[LintViolation] = []
    handlers = {
        ast.Import: _check_import,
        ast.ImportFrom: _check_importfrom,
        ast.Call: _check_call,
    }
    for node in ast.walk(tree):
        handler = handlers.get(type(node))
        if handler is None:
            continue
        for record in handler(node, source_root_prefixes):
            violations.append({
                "path": path,
                "line": record["line"],
                "reason": record["reason"],
            })
    return violations


# --- per-node-type checkers (each returns a list of {line, reason}) -------


def _check_import(node: ast.Import, _: list[str]) -> list[dict]:
    out: list[dict] = []
    for alias in node.names:
        name = alias.name
        if name in MOCK_MODULES or name.startswith("unittest.mock"):
            out.append({
                "line": node.lineno,
                "reason": f"imports mock-family module {name!r}",
            })
    return out


def _check_importfrom(node: ast.ImportFrom, _: list[str]) -> list[dict]:
    out: list[dict] = []
    module = node.module or ""
    if module in MOCK_MODULES or module.startswith("unittest.mock"):
        out.append({
            "line": node.lineno,
            "reason": f"imports from mock-family module {module!r}",
        })
        return out
    # from unittest import mock
    if module == "unittest":
        for alias in node.names:
            if alias.name == "mock":
                out.append({
                    "line": node.lineno,
                    "reason": "imports unittest.mock",
                })
    return out


def _check_call(node: ast.Call, source_root_prefixes: list[str]) -> list[dict]:
    out: list[dict] = []
    ctor = _ctor_name(node.func)
    if ctor in MOCK_CTORS:
        out.append({
            "line": node.lineno,
            "reason": f"constructs mock object via {ctor!r}",
        })
    if _is_patch_form(node.func):
        out.append({
            "line": node.lineno,
            "reason": "uses mock.patch decorator family",
        })
    if _is_monkeypatch_setattr(node.func):
        target = _first_arg_target(node)
        if target and _matches_source_root(target, source_root_prefixes):
            out.append({
                "line": node.lineno,
                "reason": (
                    f"monkeypatch.setattr targets production module "
                    f"{target!r}"
                ),
            })
    return out


# --- pure AST helpers -----------------------------------------------------


def _ctor_name(func: ast.expr) -> str | None:
    """The "name" being invoked, for matching MOCK_CTORS.

    `Mock()` -> "Mock";  `mock.Mock()` -> "Mock";  otherwise None.
    """
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _is_patch_form(func: ast.expr) -> bool:
    """Decorator-call shapes for the mock.patch family:
        @patch(...)              -> Name("patch")
        @patch.object(...)       -> Attribute(value=Name("patch"), attr="object")
        @mock.patch(...)         -> Attribute(value=Name("mock"), attr="patch")
        @mock.patch.object(...)  -> Attribute(value=<above>, attr="object")
    """
    if isinstance(func, ast.Name):
        return func.id == "patch"
    if not isinstance(func, ast.Attribute):
        return False
    # X.patch
    if func.attr == "patch":
        return True
    # X.patch.object
    if func.attr == "object" and isinstance(func.value, ast.Attribute):
        return func.value.attr == "patch"
    # patch.object  (value is Name("patch"))
    if func.attr == "object" and isinstance(func.value, ast.Name):
        return func.value.id == "patch"
    return False


def _is_monkeypatch_setattr(func: ast.expr) -> bool:
    return (
        isinstance(func, ast.Attribute)
        and func.attr == "setattr"
        and isinstance(func.value, ast.Name)
        and func.value.id == "monkeypatch"
    )


def _first_arg_target(call: ast.Call) -> str | None:
    """Dotted-name string for the first arg of monkeypatch.setattr.

    Handles two shapes the spec calls out (OPEN-1):
      setattr("apps.x.y", value)   -> "apps.x.y"
      setattr(apps.x, "y", value)  -> "apps.x"
    """
    if not call.args:
        return None
    first = call.args[0]
    if isinstance(first, ast.Constant) and isinstance(first.value, str):
        return first.value
    return _dotted_name(first)


def _dotted_name(node: ast.expr) -> str | None:
    """Reconstruct a dotted name from a Name/Attribute chain, or None."""
    parts: list[str] = []
    cur: ast.expr = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if not isinstance(cur, ast.Name):
        return None
    parts.append(cur.id)
    return ".".join(reversed(parts))


def _matches_source_root(target: str, prefixes: list[str]) -> bool:
    return any(target == p or target.startswith(p + ".") for p in prefixes)


def lint_path(
    path: str,
    source_root_prefixes: list[str],
) -> list[LintViolation]:
    """Boundary: read the file and call find_violations."""
    source = Path(path).read_text()
    return find_violations(source, path, source_root_prefixes)
