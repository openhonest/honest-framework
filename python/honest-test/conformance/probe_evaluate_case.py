"""Honest probe for honest-test's evaluate_case (feature Scenario:
evaluate_case opens the value-oracle door to run one portable suite case).

evaluate_case is the value-oracle door a sibling module's conformance runner
enters by import. It hands the case and the function map to run_case and returns
what run_case returned: honest-type's ok Result carrying the output when it
equals the expected value, honest-type's err Result carrying an expected-vs-got
fault when they differ, and a honest-test Fault when a named function or
expression is unknown (.hd evaluate_case; architecture section 8.6).

The function under test is a real pure function defined here and named in the
map. Each verdict is recognized by its shape: an ok Result carries an "ok" key,
an err Result carries an "err" key, and a honest-test Fault carries "problem" and
"remedy". No classes, no stand-ins: the map holds the real function, and the only
thing varied across cases is the expected value and whether the named symbol is
in the map.
"""

from honest_test import evaluate_case


def _is_ok(result):
    return isinstance(result, dict) and "ok" in result


def _is_err(result):
    return isinstance(result, dict) and "err" in result


def _is_ht_fault(result):
    return isinstance(result, dict) and "problem" in result and "remedy" in result


def _square(n):
    """A real pure function under test: it returns the square of its input."""
    return n * n


def probe_evaluate_case():
    """evaluate_case returns ok when the output equals expected, err when it
    differs, and a honest-test Fault when the case names an unknown symbol."""
    bad = []
    function_map = {"square": _square}

    holds = evaluate_case({"function": "square", "input": 5, "expected": 25}, function_map)
    if not _is_ok(holds):
        bad.append(f"a case whose function returns the expected value should return an ok Result, got {holds!r}")
    elif holds.get("ok") != 25:
        bad.append(f"the ok Result should carry the output 25, got {holds.get('ok')!r}")

    differs = evaluate_case({"function": "square", "input": 5, "expected": 99}, function_map)
    if not _is_err(differs):
        bad.append(f"a case whose expected value differs from the output should return an err Result, got {differs!r}")

    unknown_fn = evaluate_case({"function": "cube", "input": 5, "expected": 125}, function_map)
    if not _is_ht_fault(unknown_fn):
        bad.append(f"a case naming a function the map does not hold should return a honest-test Fault, got {unknown_fn!r}")

    unknown_ref = evaluate_case({"function": "square", "args": [{"$ref": "absent"}], "expected": 1}, function_map)
    if not _is_ht_fault(unknown_ref):
        bad.append(f"a case naming an expression the map does not hold should return a honest-test Fault, got {unknown_ref!r}")

    return bad


def run():
    messages = probe_evaluate_case()
    for message in messages:
        print(f"FAIL HT-probe [evaluate_case]: {message}")
    passed = 0 if messages else 1
    print(f"evaluate_case: {passed} passed, {len(messages)} failed")
    return 0 if not messages else 1


if __name__ == "__main__":
    raise SystemExit(run())
