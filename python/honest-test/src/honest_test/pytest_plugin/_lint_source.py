"""M2.4 silent-default lint for production source files.

Rejects functions whose signature declares a correctness-critical
parameter (user_id, workspace_id, pool, db, connection, ...) with an
empty-string or None default. Such defaults cause failures three frames
deep, with a stack pointing at the wrong function.

Companion to M2.2 (mock-family lint of test files); they share the same
collection-time AST mechanism but scan disjoint file sets.
"""
from __future__ import annotations

import ast
from typing import Callable, Iterable

from honest_test.pytest_plugin._types import SilentDefaultViolation


ALLOW_MARKER = "# allow-empty-default-required"


def find_silent_default_violations(
    source: str,
    path: str,
    params: list[str],
    values: list[str],
    exempt: list[str],
) -> list[SilentDefaultViolation]:
    """Pure: AST-walk `source`, return all silent-default violations.

    Returns empty list if `params` is empty (lint is opt-in).
    """
    if not params:
        return []
    tree = ast.parse(source)
    source_lines = source.splitlines()
    param_set = frozenset(params)
    exempt_set = frozenset(exempt)
    violations: list[SilentDefaultViolation] = []
    for fn_node in _walk_functions(tree):
        if f"{path}:{fn_node.name}" in exempt_set:
            continue
        if _has_allow_marker(source_lines, fn_node.lineno):
            continue
        signature = _render_signature(fn_node)
        for arg, default in _arg_default_pairs(fn_node):
            if arg.arg not in param_set:
                continue
            matched = _matched_sentinel(default, values)
            if matched is None:
                continue
            violations.append({
                "path": path,
                "line": fn_node.lineno,
                "function_name": fn_node.name,
                "param_name": arg.arg,
                "default_text": ast.unparse(default),
                "signature": signature,
            })
    return violations


def render_silent_default_report(
    violations: list[SilentDefaultViolation],
) -> str:
    """Pure: format the silent-default block per spec."""
    if not violations:
        return ""
    lines = ["honest_test silent-default lint", "=" * 31]
    grouped: dict[
        tuple[str, int, str, str],
        list[SilentDefaultViolation],
    ] = {}
    for v in violations:
        key = (v["path"], v["line"], v["function_name"], v["signature"])
        grouped.setdefault(key, []).append(v)
    for (path, line, _fn, signature), params in sorted(grouped.items()):
        lines.append(f"{path}:{line}")
        lines.append(f"  {signature}")
        for v in params:
            lines.append(
                f"    {v['param_name']}: "
                f"{_explain_default(v['default_text'])}"
            )
    files = len({v["path"] for v in violations})
    lines.append("")
    lines.append(
        f"Total: {len(violations)} violations across {files} files"
    )
    return "\n".join(lines)


# --- AST helpers ---------------------------------------------------------


def _walk_functions(
    tree: ast.AST,
) -> Iterable[ast.FunctionDef | ast.AsyncFunctionDef]:
    """Yield every FunctionDef/AsyncFunctionDef anywhere in the tree.

    `ast.walk` covers top-level functions, class methods, and nested
    functions in one pass. Spec acceptance #6 requires class methods.
    """
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node


def _arg_default_pairs(
    fn_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> Iterable[tuple[ast.arg, ast.expr]]:
    """Yield (arg, default_expr) for every parameter that has a default.

    `args.defaults` aligns to the TAIL of `posonlyargs + args`.
    `args.kw_defaults` aligns 1:1 with `kwonlyargs` (None = no default).
    """
    args = fn_node.args
    pos = list(args.posonlyargs) + list(args.args)
    n = len(args.defaults)
    if n:
        for arg, default in zip(pos[-n:], args.defaults):
            yield (arg, default)
    for arg, default in zip(args.kwonlyargs, args.kw_defaults):
        if default is not None:
            yield (arg, default)


def _has_allow_marker(source_lines: list[str], lineno: int) -> bool:
    """Pure: does the def line carry the escape marker?

    `lineno` is 1-based. Returns False for out-of-range linenos.
    """
    if lineno < 1 or lineno > len(source_lines):
        return False
    return ALLOW_MARKER in source_lines[lineno - 1]


def _render_signature(
    fn_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> str:
    """Pure: ast.unparse(args), wrapped with the function name."""
    args_text = ast.unparse(fn_node.args)
    return f"{fn_node.name}({args_text})"


# --- sentinel matching (dict-lookup polymorphism over if/elif) ----------


def _is_none(default: ast.expr) -> bool:
    return isinstance(default, ast.Constant) and default.value is None


def _is_empty_str(default: ast.expr) -> bool:
    return (
        isinstance(default, ast.Constant)
        and isinstance(default.value, str)
        and default.value == ""
    )


_SENTINEL_CHECKS: dict[str, Callable[[ast.expr], bool]] = {
    "None": _is_none,
    "": _is_empty_str,
}


def _matched_sentinel(default: ast.expr, values: list[str]) -> str | None:
    """Return the first value in `values` that matches `default`, or
    None. `""` and `"None"` are matched structurally; anything else
    falls back to ast.unparse equality.
    """
    for value in values:
        check = _SENTINEL_CHECKS.get(value)
        if check is not None:
            if check(default):
                return value
            continue
        if ast.unparse(default) == value:
            return value
    return None


_DEFAULT_EXPLANATIONS = {
    "''": "empty-string default on correctness-critical parameter",
    "None": "None default on correctness-critical parameter",
}


def _explain_default(default_text: str) -> str:
    return _DEFAULT_EXPLANATIONS.get(
        default_text,
        f"silent default {default_text!r} on "
        f"correctness-critical parameter",
    )
