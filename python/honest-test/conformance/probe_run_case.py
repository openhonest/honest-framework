"""Honest probe for honest-test's run_case (feature Scenario: run_case drives
the value-oracle sequence for one case).

run_case is the value-oracle orchestrator. It resolves the case with resolve_call;
when resolution returns a Fault — a named function or expression the map does not
hold — it passes the Fault outward and runs nothing. Otherwise it runs the
resolved call at the boundary, judges the output against the resolved expected
value, and returns honest-type's ok or err Result (.hd run_case; architecture
section 8.6).

Two things are asserted: the ok/err verdict on a resolvable case, and the one
decision run_case holds — a case that cannot resolve never runs. The second is
observed with a real function that records each call it receives: when the case's
argument names an absent symbol, resolution fails, and the recorder must stay
empty because run_case ran nothing.
"""

from honest_test import run_case


def _is_ok(result):
    return isinstance(result, dict) and "ok" in result


def _is_err(result):
    return isinstance(result, dict) and "err" in result


def _is_ht_fault(result):
    return isinstance(result, dict) and "problem" in result and "remedy" in result


def _square(n):
    """A real pure function under test: it returns the square of its input."""
    return n * n


def probe_run_case():
    """run_case returns ok on a matching case, err on a mismatching one, and
    passes a resolution Fault outward without running the function under test."""
    bad = []

    calls = []

    def _recording_identity(value):
        """A real function that records each call, to witness whether run_case ran it."""
        calls.append(value)
        return value

    function_map = {"square": _square, "identity": _recording_identity}

    holds = run_case({"function": "square", "input": 6, "expected": 36}, function_map)
    if not _is_ok(holds):
        bad.append(f"a case whose function returns the expected value should return an ok Result, got {holds!r}")
    elif holds.get("ok") != 36:
        bad.append(f"the ok Result should carry the output 36, got {holds.get('ok')!r}")

    differs = run_case({"function": "square", "input": 6, "expected": 35}, function_map)
    if not _is_err(differs):
        bad.append(f"a case whose expected value differs from the output should return an err Result, got {differs!r}")

    unresolvable = run_case({"function": "identity", "args": [{"$ref": "absent"}], "expected": 1}, function_map)
    if not _is_ht_fault(unresolvable):
        bad.append(f"a case whose argument names an absent symbol should pass a honest-test Fault outward, got {unresolvable!r}")
    if calls:
        bad.append(f"a case that could not resolve must run nothing, but the function under test was called with {calls!r}")

    return bad


def run():
    messages = probe_run_case()
    for message in messages:
        print(f"FAIL HT-probe [run_case]: {message}")
    passed = 0 if messages else 1
    print(f"run_case: {passed} passed, {len(messages)} failed")
    return 0 if not messages else 1


if __name__ == "__main__":
    raise SystemExit(run())
