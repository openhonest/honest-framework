"""honest-test pytest plugin (honest-test-architecture.md section 4.8, the collection-time boundary): at
collection time it fails any Python test module whose body rebinds a call target, delegating the decision
to the pure test_body_violations. Only reading the module source is I/O — the verdict is pure, and the
failure is pytest's own CollectError so the module errors cleanly and never runs. Entry point:
pytest11 = honest_test.pytest_plugin."""
import pytest

from honest_test.testbody import test_body_violations


def rebind_report(violations):
    """The collection-failure message for a module's rebinding violations, or None when there are none.
    Pure over the violation list; each site is named by its line."""
    if not violations:
        return None
    sites = "; ".join(f"line {violation['line']}: {violation['message']}" for violation in violations)
    return f"honest-test 4.8 — this test rebinds a call target at runtime, so it does not exercise the production call graph. {sites}"


def pytest_pycollect_makemodule(module_path, parent):
    """pytest collection hook (the section 4.8 boundary): before pytest builds a test module's collector,
    read its source and fail collection with a CollectError if the body rebinds a call target. The verdict
    is the pure test_body_violations; only the source read is I/O. Returning nothing lets pytest build the
    module normally."""
    report = rebind_report(test_body_violations(module_path.read_text(encoding="utf-8")))
    if report is not None:
        raise pytest.Collector.CollectError(report)
