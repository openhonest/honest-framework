#!/usr/bin/env python
"""value-check — the value-oracle gate.

Runs every module's suite.json `value_case`s through honest-test's value oracle (honest-test §8.6)
and fails if any value case is not proved. This is the cross-module counterpart to each module's own
conformance: a module cannot run the oracle on itself (honest-test depends on it, so importing the
oracle in the module's own runner would be a cycle), so the value contract is checked here, centrally,
where honest-test is available. A function with no value case is fine — it is simply not yet backfilled
(or is exempt / internal, §8.5); only a value case that is wrong or broken fails the gate.

  uv run python value-check.py
"""
import json
import sys

from honest_test import run_value_cases
from proof_run import BUILT, PY, value_function_map


def main():
    total = 0
    failures = []
    for module in BUILT:
        suite = PY / f"honest-{module}" / "conformance" / "suite.json"
        if not suite.exists():
            continue
        cases = json.loads(suite.read_text()).get("cases", [])
        function_map = value_function_map(module)
        value_cases = [
            {**case["value_case"], "id": case["id"]}
            for case in cases
            if "value_case" in case and case["value_case"]["function"] in function_map
        ]
        for result in run_value_cases(value_cases, function_map):
            total += 1
            if not result["proved"]:
                failures.append((module, result))
    for module, result in failures:
        print(f"value-check: FAIL honest-{module} {result['id']}: {result['fault']}", file=sys.stderr)
    print(f"value-check: {total - len(failures)}/{total} value cases proved across the public surfaces.")
    if failures:
        print("value-check: a value case asserts the wrong output, or its function/fixture is unresolved.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
