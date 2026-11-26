"""honest-test conformance runner (the test-of-record).

Each `probe_<function>.py` holds one pure probe: it calls the real
`honest_test.<function>` with data-defined inputs and real injected functions,
and returns a list of failure strings (empty when the function is honest). This
runner imports every probe and runs it, so one command proves the whole module.

A fault or finding is recognized by its own record shape, never by an ok/err
envelope and never raised: honest-test's Fault is `{problem, remedy}`, its
Finding carries a `code` and a `kind`, and honest-type's Result shapes are what
the value oracle compares.

  uv run --package honest-test python honest-test/conformance/run_conformance.py
"""

import importlib
import os
import sys
from pathlib import Path

_HERE = Path(__file__).parent


def run(stop_on_failure):
    sys.path.insert(0, str(_HERE))
    names = sorted(path.stem for path in _HERE.glob("probe_*.py"))
    if stop_on_failure:
        # A complete CLI integration calls generators repeatedly. Let their narrow
        # probes report failures first, before the integration can hit a bound.
        names.sort(key=lambda name: name == "probe_run_suite")
    failed = 0
    for name in names:
        module = importlib.import_module(name)
        if module.run():
            failed += 1
            # Section 9.6 requires one observed failure. A subsequent stalled probe
            # must not replace an already observed failure with a timeout.
            if stop_on_failure:
                return 1
    passed = len(names) - failed
    print(f"honest-test conformance: {passed} passed, {failed} failed, {len(names)} total")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(run(os.environ.get("HONEST_MUTATION") == "1"))
