"""honest-auth conformance runner.

honest-auth's portable contract (suite.json) is value_cases over its data-pure functions — auth_fault
and the three per-class outcome checkers — checked centrally by value-check.py (honest-test §8.6). The
laws here drive the functions that compose a provider's injected callables (registration, the boundary
flow, the honesty verifier, the determinism check), which a value case cannot express, and carry the
per-module gate to 100% coverage.

  uv run --package honest-auth python honest-auth/conformance/run_conformance.py
"""

from honest_auth import (
    _expect_actor,
    _expect_recognizer_reject,
    _expect_unauthenticated,
)
from honest_auth.types import auth_fault

# The value-oracle function map proof_run and value-check.py read. auth_fault and the three per-class
# outcome checkers are reached only by invokes or the dispatch table, so they are importable attributes
# but not in __all__ (honest-auth-architecture.md §4.7). The portable value cases name them directly, so
# the map exposes them to the central oracle while the package surface stays the seven import entries.
_VALUE_FUNCTIONS = {
    "auth_fault": auth_fault,
    "_expect_actor": _expect_actor,
    "_expect_unauthenticated": _expect_unauthenticated,
    "_expect_recognizer_reject": _expect_recognizer_reject,
}


def run(_suite_path=None):
    """No data cases to run here — the portable cases are all value cases (checked by value-check.py)."""
    return 0


if __name__ == "__main__":
    import laws_ha

    raise SystemExit(run() or laws_ha.run())
