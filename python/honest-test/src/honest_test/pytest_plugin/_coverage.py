"""M2.3 contract coverage. Pure analyzers; pytest hook wires the I/O.

A public top-level function `fn` in a configured source root is "pinned"
iff there exists a collected pytest item whose test module references the
name `fn` AND whose test function body contains at least one `assert`.

This is intentionally coarse. See SPEC-M2.md §M2.3.
"""
from __future__ import annotations

import ast
import fnmatch
from pathlib import Path

from honest_test.pytest_plugin._types import CoverageReport, CoverageRow


# --- pure analyzers -------------------------------------------------------


def find_public_functions(
    source: str,
    private_functions: str = "skip",
) -> list[str]:
    """Pure: top-level function names from a module source string.

    `private_functions="skip"` (default) drops names starting with `_`.
    `private_functions="include"` keeps them.
    """
    tree = ast.parse(source)
    keep = _PRIVATE_POLICY.get(private_functions, _keep_public)
    return [
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and keep(node.name)
    ]


def names_referenced(source: str) -> set[str]:
    """Pure: every identifier the module's AST mentions.

    Captures Name.id, Attribute.attr, and the imported aliases. Coarse
    on purpose — the spec wants a strict superset of actually-tested.
    """
    tree = ast.parse(source)
    names: set[str] = set()
    for node in ast.walk(tree):
        collector = _NAME_COLLECTORS.get(type(node))
        if collector is not None:
            collector(node, names)
    return names


def function_has_assert(source: str, function_name: str) -> bool:
    """Pure: does the named top-level def contain any `assert`?

    Returns False if the function is absent.
    """
    tree = ast.parse(source)
    target = next(
        (
            node for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == function_name
        ),
        None,
    )
    if target is None:
        return False
    return any(isinstance(sub, ast.Assert) for sub in ast.walk(target))


def is_excluded(path: str, patterns: list[str]) -> bool:
    """Pure: does `path` match any user-supplied exclude glob?"""
    return any(fnmatch.fnmatch(path, "*" + pat + "*") for pat in patterns)


# Directory names that are NEVER scanned for source coverage, regardless
# of user config. These are conventional caches, vendored deps, and
# virtualenvs — counting their files would massively inflate the
# denominator (a single .venv can contain tens of thousands of .py files
# from site-packages). Users cannot opt back in; if they really want
# something in this list scanned, they should move it out of the source
# root.
DEFAULT_EXCLUDED_DIR_NAMES = frozenset({
    ".venv",
    "venv",
    "env",
    ".env",
    "__pycache__",
    ".ruff_cache",
    ".mypy_cache",
    ".pytest_cache",
    ".tox",
    ".nox",
    ".git",
    ".hg",
    ".svn",
    "node_modules",
    "dist",
    "build",
    ".eggs",
    "site-packages",
})


def has_excluded_dir_part(path: Path, excluded: frozenset[str]) -> bool:
    """Pure: True if any path component matches the excluded-dir set."""
    return any(part in excluded for part in path.parts)


# --- aggregation ----------------------------------------------------------


def compute_coverage(
    source_files: dict[str, str],
    test_modules: dict[str, str],
    asserting_items: list[tuple[str, str]],
    private_functions: str = "skip",
) -> CoverageReport:
    """Pure: combine sources, test modules, and asserting items into a
    CoverageReport.

    `source_files`: {source_path: source_text} for production code under
                    the configured source roots.
    `test_modules`: {test_path: test_text} for every test module that
                    contributed at least one item.
    `asserting_items`: list of (test_path, test_func_name) for items
                       whose body contains an assert.
    """
    pinned_names = _pinned_name_universe(test_modules, asserting_items)
    rows: list[CoverageRow] = []
    total_pinned = 0
    total_functions = 0
    for path in sorted(source_files):
        fns = find_public_functions(source_files[path], private_functions)
        marks = [(fn, fn in pinned_names) for fn in fns]
        pinned = sum(1 for _, p in marks if p)
        rows.append({
            "file": path,
            "pinned": pinned,
            "total": len(fns),
            "function_names": marks,
        })
        total_pinned += pinned
        total_functions += len(fns)
    return {
        "rows": rows,
        "total_pinned": total_pinned,
        "total_functions": total_functions,
    }


def _pinned_name_universe(
    test_modules: dict[str, str],
    asserting_items: list[tuple[str, str]],
) -> set[str]:
    """Names referenced by any test module that contains at least one
    asserting item. The spec's intent: a name is pinned if some asserting
    test references it.
    """
    asserting_modules = {path for path, _ in asserting_items}
    universe: set[str] = set()
    for path in asserting_modules:
        source = test_modules.get(path)
        if source is None:
            continue
        universe |= names_referenced(source)
    return universe


# --- rendering ------------------------------------------------------------


def render_coverage_report(report: CoverageReport) -> str:
    """Pure: format the coverage block per spec."""
    lines = ["honest contract coverage", "========================"]
    grouped: dict[str, list[CoverageRow]] = {}
    for row in report["rows"]:
        directory = str(Path(row["file"]).parent) + "/"
        grouped.setdefault(directory, []).append(row)
    for directory in sorted(grouped):
        lines.append(directory)
        for row in grouped[directory]:
            name = Path(row["file"]).name
            pct = _percent(row["pinned"], row["total"])
            lines.append(
                f"  {name:30s}{row['pinned']:3d} pinned / "
                f"{row['total']:3d} functions ({pct:3.0f}%)"
            )
    total_pct = _percent(report["total_pinned"], report["total_functions"])
    lines.append(
        f"\nTotal: {report['total_pinned']} pinned / "
        f"{report['total_functions']} functions ({total_pct:.0f}%)"
    )
    return "\n".join(lines)


def _percent(num: int, denom: int) -> float:
    return (num / denom * 100.0) if denom else 0.0


# --- dispatch tables (honest-code: no if/elif on values) ------------------


def _keep_public(name: str) -> bool:
    return not name.startswith("_")


def _keep_any(_: str) -> bool:
    return True


_PRIVATE_POLICY = {
    "skip": _keep_public,
    "include": _keep_any,
}


def _collect_name(node: ast.AST, names: set[str]) -> None:
    names.add(node.id)  # type: ignore[attr-defined]


def _collect_attr(node: ast.AST, names: set[str]) -> None:
    names.add(node.attr)  # type: ignore[attr-defined]


def _collect_import(node: ast.AST, names: set[str]) -> None:
    for alias in node.names:  # type: ignore[attr-defined]
        names.add(alias.asname or alias.name.split(".")[0])


def _collect_importfrom(node: ast.AST, names: set[str]) -> None:
    for alias in node.names:  # type: ignore[attr-defined]
        names.add(alias.asname or alias.name)


_NAME_COLLECTORS = {
    ast.Name: _collect_name,
    ast.Attribute: _collect_attr,
    ast.Import: _collect_import,
    ast.ImportFrom: _collect_importfrom,
}


# --- I/O at the boundary --------------------------------------------------


def discover_source_files(
    source_roots: list[str],
    exclude_patterns: list[str],
    rootpath: Path,
) -> dict[str, str]:
    """Boundary: walk source roots and read every .py file, skipping
    venvs, caches, vendored deps, and user-configured exclude patterns.
    """
    found: dict[str, str] = {}
    for root in source_roots:
        root_path = (rootpath / root).resolve()
        if not root_path.is_dir():
            continue
        for py in root_path.rglob("*.py"):
            if has_excluded_dir_part(py, DEFAULT_EXCLUDED_DIR_NAMES):
                continue
            rel = str(py)
            if is_excluded(rel, exclude_patterns):
                continue
            found[rel] = py.read_text()
    return found
