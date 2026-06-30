"""honest-auth conformance runner.

honest-auth's portable contract (suite.json) is all `value_case`s, checked centrally by value-check.py
(honest-test §8.6). The laws here exercise the functions that take live callables — a provider's
recognizer and resolver — which a JSON value case cannot carry, and drive 100% coverage of the module.

  uv run --package honest-auth python honest-auth/conformance/run_conformance.py
"""

import sys


def run(_suite_path=None):
    """No data cases to run — the portable cases are all value cases (checked by value-check.py)."""
    return 0


if __name__ == "__main__":
    import laws_ha

    raise SystemExit(run() or laws_ha.run())
