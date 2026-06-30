"""honest-features conformance runner.

honest-features's portable contract (suite.json) is value cases, checked centrally by value-check.py
(honest-test §8.6). The laws here pin the same surface for the per-module gate and drive 100% coverage,
including the HMAC signature round trip — which a JSON value case cannot carry because the secret is bytes.

  uv run --package honest-features python honest-features/conformance/run_conformance.py
"""


def run(_suite_path=None):
    """No data cases to run — the portable cases are all value cases (checked by value-check.py)."""
    return 0


if __name__ == "__main__":
    import laws_hf

    raise SystemExit(run() or laws_hf.run())
