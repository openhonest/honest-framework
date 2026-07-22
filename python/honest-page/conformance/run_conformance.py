"""honest-page conformance runner: the reference's structural, bootstrap, SSE, and intake contracts
(spec section 11.2), checked against the templates and server the spec names as normative.

  uv run python honest-page/conformance/run_conformance.py
"""

import sys


if __name__ == "__main__":
    import laws_hp

    raise SystemExit(laws_hp.run())
