# bootstrap-exempt: root conformance harness; the subagent chain cannot produce the aggregator that wires the per-scenario laws files into one gate entry.
"""honest-alerts conformance runner.

honest-alerts's portable contract (suite.json) is value cases, checked centrally by value-check.py
(honest-test section 8.6). The behavioural laws are one file per feature scenario, named
`laws_<scenario_subject>.py` beside this runner (the live laws_*.py form; one scenario per file so the
test-author fan-out never collides). This runner imports each of them in-process and runs it, so
coverage-all, which executes this file under branch coverage, exercises every scenario's test and the
module lines they reach.

Each `laws_*.py` fragment exposes either a `run()` returning an exit code (0 green, non-zero red) or
one or more `probe_*()` functions returning a list of failure strings; a probe may be async. This
runner handles both shapes and treats an import error, a raised exception, a truthy run() code, or a
non-empty probe result as a red for that scenario.

The stale `laws_ha.py` (the pre-rebuild single-file laws) is excluded: honest-coder replaces it as part
of the rebuild. It is left in place, untouched, and does not run here.

  uv run --package honest-alerts python honest-alerts/conformance/run_conformance.py
"""

import asyncio
import importlib
import inspect
import pathlib

from honest_alerts import advance, build_message, is_terminated, mailbox


# Keep the current value cases independent of the package's advertised exports.
_VALUE_FUNCTIONS = {
    "is_terminated": is_terminated,
    "mailbox": mailbox,
    "advance": advance,
    "build_message": build_message,
}

_HERE = pathlib.Path(__file__).resolve().parent
_SKIP = {"run_conformance", "laws_ha"}


def _resolve(value):
    """A probe may be sync or async; run a coroutine to its result."""
    if inspect.iscoroutine(value):
        return asyncio.run(value)
    return value


def _run_fragment(name):
    """Import and run one laws_<scenario>.py; return a list of failure strings (empty when green)."""
    try:
        module = importlib.import_module(name)
    except Exception as exc:  # the red of an unbuilt module is an import failure on its function
        return [f"{name}: import failed: {exc!r}"]

    if hasattr(module, "run"):
        try:
            code = _resolve(module.run())
        except Exception as exc:
            return [f"{name}.run() raised: {exc!r}"]
        return [] if not code else [f"{name}.run() -> {code}"]

    probes = [getattr(module, n) for n in dir(module) if n.startswith("probe_") and callable(getattr(module, n))]
    if not probes:
        return [f"{name}: no run() and no probe_* function"]

    failures = []
    for probe in probes:
        try:
            result = _resolve(probe())
        except Exception as exc:
            failures.append(f"{name}.{probe.__name__} raised: {exc!r}")
            continue
        if result:
            for item in result:
                failures.append(f"{name}.{probe.__name__}: {item}")
    return failures


def run(_suite_path=None):
    """Run every per-scenario laws file beside this runner. 0 when all green, 1 when any is red."""
    failures = []
    for path in sorted(_HERE.glob("laws_*.py")):
        if path.stem in _SKIP:
            continue
        failures.extend(_run_fragment(path.stem))
    for line in failures:
        print(line)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(run())
