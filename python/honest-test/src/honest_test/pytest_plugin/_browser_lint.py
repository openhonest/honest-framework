"""Browser-test lint. Pure AST scanner for pytest-bdd step def files that
exercise the honest-test browser harness.

Five rules, all collection-time:

  B1 — step def has empty body (pass / docstring only). A scenario whose
       step does not assert is hollow per feedback_test_pins_one_contract.
  B2 — file contains a synthetic-event JS string (dispatchEvent,
       new MouseEvent / KeyboardEvent / PointerEvent / DragEvent,
       evaluate-wrapped .click / .focus / .dispatchEvent). Synthetic
       events bypass the real input pipeline; see no_synthetic_events.
  B3 — step def's signature does not request the required harness fixture.
       Bypassing the harness means console / network errors are not
       captured; see proxy_verification.
  B4 — file imports a forbidden symbol (default: Page, auth_page). Binding
       these names is the most common way to reach past the harness.
  B5 — step def calls request.getfixturevalue("<auth_fixture>") to grab
       the raw page directly, bypassing the harness's console capture.

`find_browser_violations` is pure; the pytest hook (`__init__.py`) is the
I/O boundary that reads files and raises UsageError on the first hit.
"""
from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, Iterable

from honest_test.pytest_plugin._types import BrowserLintViolation


STEP_DECORATORS = frozenset({"given", "when", "then"})

FORBIDDEN_JS_SUBSTRINGS: tuple[str, ...] = (
    "dispatchEvent(",
    "new MouseEvent(",
    "new KeyboardEvent(",
    "new PointerEvent(",
    "new DragEvent(",
    ".click(",
    ".focus(",
)


def find_browser_violations(
    source: str,
    path: str,
    config: dict[str, Any],
) -> list[BrowserLintViolation]:
    """Pure: AST-walk `source` and return every browser-lint violation.

    Reads three keys from `config`:
      - browser_required_fixture (str, default "harness")  -> B3
      - browser_auth_fixture     (str, default "page")     -> B5
      - browser_forbidden_imports (list[str], default
        ["Page", "auth_page"])                             -> B4
    """
    required = config.get("browser_required_fixture", "harness")
    auth = config.get("browser_auth_fixture", "page")
    forbidden_imports = config.get(
        "browser_forbidden_imports", ["Page", "auth_page"],
    )

    tree = ast.parse(source)
    violations: list[BrowserLintViolation] = []
    violations.extend(_check_file_imports(tree, path, forbidden_imports))
    violations.extend(_check_file_js_strings(tree, path))
    for fn in _walk_functions(tree):
        if not _is_step_def(fn):
            continue
        violations.extend(_check_step_empty_body(fn, path))
        violations.extend(_check_step_missing_fixture(fn, path, required))
        violations.extend(_check_step_getfixturevalue(fn, path, auth))
    violations.sort(key=lambda v: (v["line"], v["rule"]))
    return violations


def lint_browser_path(
    path: str,
    config: dict[str, Any],
) -> list[BrowserLintViolation]:
    """Boundary: read the file and call `find_browser_violations`."""
    source = Path(path).read_text()
    return find_browser_violations(source, path, config)


def in_browser_step_roots(path: str, roots: list[str]) -> bool:
    """Pure: True iff `path` lives under any of the given root prefixes.

    Compares by path components, not raw string prefix, so
    "tests/playwright/step_defs" does not falsely match
    "tests/playwright/step_defs_helpers/x.py". Works for both absolute
    and relative `path` inputs.
    """
    if not roots:
        return False
    p_parts = Path(path).parts
    for root in roots:
        r_parts = Path(root).parts
        if not r_parts or len(r_parts) > len(p_parts):
            continue
        for i in range(len(p_parts) - len(r_parts) + 1):
            if p_parts[i : i + len(r_parts)] == r_parts:
                return True
    return False


# --- per-rule checkers ----------------------------------------------------


def _check_file_imports(
    tree: ast.AST,
    path: str,
    forbidden: list[str],
) -> list[BrowserLintViolation]:
    out: list[BrowserLintViolation] = []
    forbidden_set = frozenset(forbidden)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name in forbidden_set:
                    out.append({
                        "path": path,
                        "line": node.lineno,
                        "rule": "B4",
                        "reason": (
                            f"forbidden import {alias.name!r} "
                            f"(from {node.module or '?'!r}): binding this "
                            f"name lets a step def bypass the harness"
                        ),
                    })
        elif isinstance(node, ast.Import):
            for alias in node.names:
                # `import X.Y` -> dotted; the bound short name is the leaf
                # if no `as` alias.
                short = (alias.asname or alias.name).split(".")[-1]
                if alias.name in forbidden_set or short in forbidden_set:
                    out.append({
                        "path": path,
                        "line": node.lineno,
                        "rule": "B4",
                        "reason": (
                            f"forbidden import {alias.name!r}: binding "
                            f"this name lets a step def bypass the harness"
                        ),
                    })
    return out


def _check_file_js_strings(
    tree: ast.AST,
    path: str,
) -> list[BrowserLintViolation]:
    out: list[BrowserLintViolation] = []
    seen: set[tuple[int, str]] = set()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
            continue
        text = node.value
        for substring in FORBIDDEN_JS_SUBSTRINGS:
            if substring not in text:
                continue
            key = (node.lineno, substring)
            if key in seen:
                continue
            seen.add(key)
            out.append({
                "path": path,
                "line": node.lineno,
                "rule": "B2",
                "reason": (
                    f"forbidden synthetic-event pattern "
                    f"{substring!r} in a string literal: use the harness "
                    f"(UserAction) for real input instead"
                ),
            })
    return out


def _check_step_empty_body(
    fn: ast.FunctionDef | ast.AsyncFunctionDef,
    path: str,
) -> list[BrowserLintViolation]:
    if not _has_empty_body(fn):
        return []
    return [{
        "path": path,
        "line": fn.lineno,
        "rule": "B1",
        "reason": (
            f"step def {fn.name!r} has empty body: a step that does not "
            f"assert is not a contract (test_pins_one_contract)"
        ),
    }]


def _check_step_missing_fixture(
    fn: ast.FunctionDef | ast.AsyncFunctionDef,
    path: str,
    required: str,
) -> list[BrowserLintViolation]:
    arg_names = _arg_names(fn)
    if required in arg_names:
        return []
    return [{
        "path": path,
        "line": fn.lineno,
        "rule": "B3",
        "reason": (
            f"step def {fn.name!r} does not request the required "
            f"{required!r} fixture: the harness must be in scope to "
            f"capture console / failed-request errors"
        ),
    }]


def _check_step_getfixturevalue(
    fn: ast.FunctionDef | ast.AsyncFunctionDef,
    path: str,
    auth_fixture: str,
) -> list[BrowserLintViolation]:
    out: list[BrowserLintViolation] = []
    for node in ast.walk(fn):
        if not isinstance(node, ast.Call):
            continue
        if not _is_getfixturevalue_call(node.func):
            continue
        if not node.args:
            continue
        first = node.args[0]
        if not (isinstance(first, ast.Constant) and isinstance(first.value, str)):
            continue
        if first.value != auth_fixture:
            continue
        out.append({
            "path": path,
            "line": node.lineno,
            "rule": "B5",
            "reason": (
                f"step def {fn.name!r} grabs the auth fixture "
                f"{auth_fixture!r} via request.getfixturevalue: that "
                f"bypasses the harness's console-error capture"
            ),
        })
    return out


# --- AST helpers ----------------------------------------------------------


def _walk_functions(
    tree: ast.AST,
) -> Iterable[ast.FunctionDef | ast.AsyncFunctionDef]:
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node


def _is_step_def(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for dec in fn.decorator_list:
        name = _decorator_name(dec)
        if name in STEP_DECORATORS:
            return True
    return False


def _decorator_name(dec: ast.expr) -> str | None:
    """The leaf-name of a decorator expression, ignoring module qualification.

    @given("...")          -> "given"
    @parsers.given("...")  -> "given"
    @bdd.when              -> "when"
    """
    if isinstance(dec, ast.Call):
        return _decorator_name(dec.func)
    if isinstance(dec, ast.Attribute):
        return dec.attr
    if isinstance(dec, ast.Name):
        return dec.id
    return None


def _has_empty_body(
    fn: ast.FunctionDef | ast.AsyncFunctionDef,
) -> bool:
    body = fn.body
    if not body:
        return True
    for stmt in body:
        if isinstance(stmt, ast.Pass):
            continue
        if (
            isinstance(stmt, ast.Expr)
            and isinstance(stmt.value, ast.Constant)
            and isinstance(stmt.value.value, str)
        ):
            continue
        return False
    return True


def _arg_names(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    args = fn.args
    names: set[str] = set()
    for arg in args.posonlyargs:
        names.add(arg.arg)
    for arg in args.args:
        names.add(arg.arg)
    for arg in args.kwonlyargs:
        names.add(arg.arg)
    if args.vararg:
        names.add(args.vararg.arg)
    if args.kwarg:
        names.add(args.kwarg.arg)
    return names


def _is_getfixturevalue_call(func: ast.expr) -> bool:
    """Match `request.getfixturevalue(...)` and `<x>.getfixturevalue(...)`.

    Restricted to `getfixturevalue` as the attribute name; the receiver
    can be `request` or any name aliased to it.
    """
    return (
        isinstance(func, ast.Attribute)
        and func.attr == "getfixturevalue"
    )
