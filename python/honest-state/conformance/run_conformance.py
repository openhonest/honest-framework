"""honest-state conformance runner.

honest-state's portable contract (suite.json) is all `value_case`s, checked centrally by value-check.py
(honest-test §8.6). The laws here pin the same surface for the per-module gate and drive 100% coverage:
the taxonomy, the mutator lookup, and the single-mutator law.

  uv run --package honest-state python honest-state/conformance/run_conformance.py
"""

import sys


def run(_suite_path=None):
    """No data cases to run — the portable cases are all value cases (checked by value-check.py)."""
    return 0


if __name__ == "__main__":
    import laws_hs

    raise SystemExit(run() or laws_hs.run())
