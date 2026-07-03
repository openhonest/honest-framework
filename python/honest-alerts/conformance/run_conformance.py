"""honest-alerts conformance runner.

honest-alerts's portable contract (suite.json) is value cases, checked centrally by value-check.py
(honest-test §8.6). The laws here pin the same pure surface for the per-module gate and drive 100%
coverage of the mailbox projection and every termination branch.

  uv run --package honest-alerts python honest-alerts/conformance/run_conformance.py
"""


def run(_suite_path=None):
    """No data cases to run — the portable cases are all value cases (checked by value-check.py)."""
    return 0


if __name__ == "__main__":
    import laws_ha

    raise SystemExit(run() or laws_ha.run())
