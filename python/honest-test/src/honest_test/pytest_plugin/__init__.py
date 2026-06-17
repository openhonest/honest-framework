"""pytest plugin entry point for honest-test M2.

The hooks here are the I/O boundary: they read pyproject.toml, walk the
collected items, read test files, and write to the terminal. All real
work is in the pure functions of `_config`, `_count`, `_lint`, `_coverage`.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from honest_test.pytest_plugin._config import load_honest_test_config
from honest_test.pytest_plugin._count import (
    count_contracts,
    render_contract_summary,
)
from honest_test.pytest_plugin._coverage import (
    compute_coverage,
    discover_source_files,
    function_has_assert,
    render_coverage_report,
)
from honest_test.pytest_plugin._browser_lint import (
    find_browser_violations,
    in_browser_step_roots,
)
from honest_test.pytest_plugin._lint import (
    find_violations,
    is_exempt,
)
from honest_test.pytest_plugin._lint_source import (
    find_silent_default_violations,
    render_silent_default_report,
)


_CONFIG_KEY = "honest_test"
_STATE_KEY = "_honest_test_state"


def pytest_configure(config: pytest.Config) -> None:
    """Boundary: load [tool.honest_test], stash on config.

    State is held as plain dicts/TypedDicts; no class instances on config.
    """
    htc = load_honest_test_config(Path(str(config.rootpath)))
    setattr(config, _CONFIG_KEY, htc)
    setattr(config, _STATE_KEY, {
        "linted_paths": set(),
        "collected_nodeids": [],
        "contract_stats": None,
        "coverage_report": None,
        "coverage_pct": 0.0,
        "below_threshold": False,
        "silent_default_violations": [],
        "silent_default_failed": False,
    })
    config.addinivalue_line(
        "markers",
        "allow_console_errors: harness teardown ignores captured "
        "console errors / warnings for this test",
    )
    config.addinivalue_line(
        "markers",
        "allow_failed_requests: harness teardown ignores captured "
        "failed requests for this test",
    )


def pytest_collectstart(collector: pytest.Collector) -> None:
    """M2.2 mock lint + browser lint. AST-scan each Python source file
    once, before its items are produced. Raises UsageError on the first
    violation found by either scan.
    """
    config = collector.config
    htc = getattr(config, _CONFIG_KEY, None)
    state = getattr(config, _STATE_KEY, None)
    if htc is None or state is None:
        return
    do_mock_lint = htc["lint"]
    do_browser_lint = bool(htc["browser_step_roots"])
    if not do_mock_lint and not do_browser_lint:
        return
    fspath = getattr(collector, "fspath", None)
    if fspath is None:
        return
    path = str(fspath)
    if not (path.endswith(".py") and Path(path).is_file()):
        return
    linted: set[str] = state["linted_paths"]
    if path in linted:
        return
    linted.add(path)

    mock_lint_path = (
        do_mock_lint and not is_exempt(path, htc["lint_exempt"])
    )
    browser_lint_path = (
        do_browser_lint
        and in_browser_step_roots(path, htc["browser_step_roots"])
    )
    if not mock_lint_path and not browser_lint_path:
        return
    source = Path(path).read_text()
    if mock_lint_path:
        violations = find_violations(source, path, htc["source_roots"])
        if violations:
            first = violations[0]
            raise pytest.UsageError(
                f"honest_test lint: "
                f"{first['path']}:{first['line']}: {first['reason']}"
            )
    if browser_lint_path:
        browser_violations = find_browser_violations(source, path, htc)
        if browser_violations:
            first = browser_violations[0]
            raise pytest.UsageError(
                f"honest_test browser_lint: "
                f"{first['path']}:{first['line']}: "
                f"[{first['rule']}] {first['reason']}"
            )


def pytest_collection_finish(session: pytest.Session) -> None:
    """Compute the M2.1 contract stats, M2.3 coverage report, and M2.4
    silent-default violations here, once. terminal_summary and
    sessionfinish are both order-independent readers of state.
    """
    config = session.config
    htc = getattr(config, _CONFIG_KEY, None)
    state = getattr(config, _STATE_KEY, None)
    if htc is None or state is None:
        return
    nodeids = [item.nodeid for item in session.items]
    state["collected_nodeids"] = nodeids
    state["contract_stats"] = count_contracts(nodeids)
    if not htc["source_roots"]:
        return
    rootpath = Path(str(config.rootpath))
    source_files = discover_source_files(
        htc["source_roots"], htc["exclude_patterns"], rootpath,
    )
    report = _build_coverage_report(htc, source_files, session.items)
    state["coverage_report"] = report
    pct = _coverage_pct(report)
    state["coverage_pct"] = pct
    state["below_threshold"] = (
        htc["coverage_fail_under"] and pct < htc["coverage_min"]
    )
    if htc["silent_default_params"]:
        violations = _collect_silent_default_violations(
            htc, source_files, rootpath,
        )
        state["silent_default_violations"] = violations
        state["silent_default_failed"] = (
            bool(violations) and htc["silent_default_fail_on_violation"]
        )


def pytest_terminal_summary(
    terminalreporter,
    exitstatus: int,
    config: pytest.Config,
) -> None:
    """M2.1 + M2.3 reporting. Pure read of precomputed state."""
    htc = getattr(config, _CONFIG_KEY, None)
    state = getattr(config, _STATE_KEY, None)
    if htc is None or state is None:
        return
    blocks: list[str] = []
    stats = state.get("contract_stats")
    if stats is not None and (
        htc["report_contracts"] or htc["report_pytest_items"]
    ):
        blocks.append(render_contract_summary(stats, htc))
    report = state.get("coverage_report")
    if report is not None:
        blocks.append(render_coverage_report(report))
        if state.get("below_threshold"):
            blocks.append(
                f"honest_test: coverage {state['coverage_pct']:.0f}% "
                f"is below coverage_min={htc['coverage_min']}"
            )
    silent_default = state.get("silent_default_violations") or []
    if silent_default:
        blocks.append(render_silent_default_report(silent_default))
    for block in blocks:
        terminalreporter.write_line("")
        for line in block.split("\n"):
            terminalreporter.write_line(line)


def pytest_sessionfinish(
    session: pytest.Session,
    exitstatus: int,
) -> None:
    """Exit-code escalation for coverage fail-under (M2.3) and
    silent-default violations (M2.4).
    """
    state = getattr(session.config, _STATE_KEY, None)
    if state is None:
        return
    fail = state.get("below_threshold") or state.get("silent_default_failed")
    if fail and exitstatus == 0:
        session.exitstatus = 1


# --- helpers (still boundary-side; they do file I/O) ----------------------


def _build_coverage_report(htc, source_files, items):
    test_paths_seen: set[str] = set()
    test_modules: dict[str, str] = {}
    asserting_items: list[tuple[str, str]] = []
    for item in items:
        test_path, func_name = _item_identity(item)
        if test_path is None or func_name is None:
            continue
        if test_path not in test_paths_seen:
            test_paths_seen.add(test_path)
            test_modules[test_path] = Path(test_path).read_text()
        if function_has_assert(test_modules[test_path], func_name):
            asserting_items.append((test_path, func_name))
    return compute_coverage(
        source_files,
        test_modules,
        asserting_items,
        htc["private_functions"],
    )


def _collect_silent_default_violations(htc, source_files, rootpath):
    """Boundary: scan each pre-loaded source for M2.4 violations.

    Path is normalised to relative-from-rootpath so the
    `silent_default_exempt` list can use familiar `apps/x/y.py:fn` keys.
    """
    out: list = []
    for abs_path, source in source_files.items():
        try:
            rel = str(Path(abs_path).relative_to(rootpath))
        except ValueError:
            rel = abs_path
        out.extend(find_silent_default_violations(
            source,
            rel,
            htc["silent_default_params"],
            htc["silent_default_values"],
            htc["silent_default_exempt"],
        ))
    return out


def _item_identity(item) -> tuple[str | None, str | None]:
    """Extract (test_file_path, top-level def name) for a pytest item.

    Falls back to nodeid parsing for items without `.module`/`.function`.
    """
    fspath = getattr(item, "fspath", None)
    path = str(fspath) if fspath is not None else None
    func = getattr(item, "function", None)
    name = getattr(func, "__name__", None) if func is not None else None
    if name is None:
        leaf = item.nodeid.split("::")[-1]
        name = leaf.split("[", 1)[0]
    return (path, name)


def _coverage_pct(report) -> float:
    total = report["total_functions"]
    if not total:
        return 100.0
    return report["total_pinned"] / total * 100.0
