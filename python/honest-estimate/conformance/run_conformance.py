"""honest-estimate conformance runner.

The suite holds the value-oracle cases (source in, SizeReport out) for the public surface; they are
proved centrally by value-check.py. The behavioural proof — every branch of the two emitters, the
widened §7.1 process rule, and the §7.3 open-vocabulary flagging — lives in laws_he.py.

  uv run --package honest-estimate python honest-estimate/conformance/run_conformance.py
"""

import json
import sys
from pathlib import Path


def run(suite_path):
    suite = json.loads(Path(suite_path).read_text(encoding="utf-8"))
    passed = 0
    failed = 0
    for case in suite["cases"]:
        if "value_case" in case:
            continue  # value cases are checked centrally by value-check.py; a module cannot run the oracle on itself
        failed += 1
        print(f"FAIL {case['id']}: honest-estimate has no non-value conformance cases")
    print(f"conformance: {passed} passed, {failed} failed, {passed + failed} total")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    import laws_he

    default = str(Path(__file__).parent / "suite.json")
    suite_status = run(sys.argv[1] if len(sys.argv) > 1 else default)
    laws_status = laws_he.run()
    raise SystemExit(suite_status or laws_status)
