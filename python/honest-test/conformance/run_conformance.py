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
import sys
from pathlib import Path

_HERE = Path(__file__).parent


def run():
    sys.path.insert(0, str(_HERE))
    names = sorted(path.stem for path in _HERE.glob("probe_*.py"))
    failed = 0
    for name in names:
        module = importlib.import_module(name)
        failed += 1 if module.run() else 0
    passed = len(names) - failed
    print(f"honest-test conformance: {passed} passed, {failed} failed, {len(names)} total")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(run())
