"""honest-persist conformance runner.

honest-persist's pure functions return bare values and bare Faults (value | Fault, honest-type
sections 12-13), with no {ok}/{err} envelope, so their exact-value oracles live in suite.json as
`value_case`s and are run centrally by value-check.py against the built public surface (the same
layering reason honest-observe and honest-gherkin give: a module cannot run the value oracle on
itself, since the oracle is honest-test, a higher layer). This runner therefore skips value cases and
reports how many are latent, then runs the behavioural laws in laws_hp.py, which carry the live signal
— today a RED one, because the code port has not run and only six of the 87 declared functions exist.

  uv run --package honest-persist python honest-persist/conformance/run_conformance.py
"""

import json
import os
import sys
from pathlib import Path

import honest_persist as _hp


def run(suite_path):
    """Report the suite's value cases: how many are active now (their function is built and exported)
    and how many are latent (awaiting the code port). A value case is never failed here; value-check.py
    proves the active ones against the built surface. This keeps the runner honest about what it did and
    did not check, rather than printing a green it did not earn."""
    suite = json.loads(Path(suite_path).read_text(encoding="utf-8"))
    cases = suite.get("cases", [])
    value_cases = [c for c in cases if "value_case" in c]
    active = [c for c in value_cases if getattr(_hp, c["value_case"]["function"], None) is not None]
    latent = len(value_cases) - len(active)
    print(f"conformance: {len(value_cases)} value cases in suite.json — {len(active)} active (function built), "
          f"{latent} latent (awaiting the code port); value-check.py proves the active ones centrally.")
    return 0


if __name__ == "__main__":
    import laws_hp

    default = str(Path(__file__).parent / "suite.json")
    suite_status = run(sys.argv[1] if len(sys.argv) > 1 else default)
    laws_status = laws_hp.run(os.environ.get("HONEST_MUTATION") == "1")
    raise SystemExit(suite_status or laws_status)
