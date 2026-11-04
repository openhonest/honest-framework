"""Conformance fragment for the evaluate_case scenario (honest-test.feature).

Scenario: evaluate_case runs one portable value-oracle case and compares the
  output against the known-good value.
  Then it builds the call from the portable case — a single `input`, positional
  `args`, or keyword `kwargs`, each entry a literal, a `$ref` naming a callable,
  or a `$call` applying a named function to its resolved arguments — invokes the
  function under test, runs an awaitable result to completion, and judges the
  output against the `expected` value: the ok Result on a match, the err Result
  carrying expected-vs-got on a mismatch, and a Fault when a named function is
  absent. This is the leg that earns a function proved (section 8.5).

Cases are data; one pure probe feeds them to the real honest_test.evaluate_case
and returns a list of failure strings (empty when every case holds). No classes,
no mocks: the functions in function_map are ordinary pure functions passed as
data. The case shape is the portable suite.json format every module uses, not a
bespoke grammar: {function, input|args|kwargs, expected} with $ref/$call.

This is its own fragment file so the other scenarios' fragments never collide
with it. run_conformance.py / laws_htest.py are untouched.
"""

from honest_test import evaluate_case


# ---- Functions under test: real pure functions injected through the map ----
def _double(n):
    """Doubles its argument."""
    return n * 2


def _add(a, b):
    """Adds two arguments — reached by positional args and by kwargs."""
    return a + b


def _apply_fn(f, x):
    """A function-taking function: applies the callable it is handed to x."""
    return f(x)


async def _aid(n):
    """An async function under test, to exercise run-to-completion."""
    return n


_MAP = {"double": _double, "add": _add, "apply_fn": _apply_fn, "aid": _aid}

_MATCH = "match"
_MISMATCH = "mismatch"
_FAULT = "fault"

_CASES = [
    # single `input`, output equals expected -> ok(42).
    {"case": {"function": "double", "input": 21, "expected": 42},
     "verdict": _MATCH, "output": 42},
    # positional `args` -> add(2, 3) -> 5 -> ok(5).
    {"case": {"function": "add", "args": [2, 3], "expected": 5},
     "verdict": _MATCH, "output": 5},
    # keyword `kwargs` -> add(a=2, b=3) -> 5 -> ok(5).
    {"case": {"function": "add", "kwargs": {"a": 2, "b": 3}, "expected": 5},
     "verdict": _MATCH, "output": 5},
    # `$ref` resolves a callable handed to a function-taking function:
    # apply_fn(double, 21) -> 42 -> ok(42).
    {"case": {"function": "apply_fn", "args": [{"$ref": "double"}, 21], "expected": 42},
     "verdict": _MATCH, "output": 42},
    # `$call` applies a named function while building an argument:
    # add($call double(10), 5) -> add(20, 5) -> 25 -> ok(25).
    {"case": {"function": "add", "args": [{"$call": "double", "args": [10]}, 5], "expected": 25},
     "verdict": _MATCH, "output": 25},
    # async function run to completion -> aid(7) -> 7 -> ok(7).
    {"case": {"function": "aid", "input": 7, "expected": 7},
     "verdict": _MATCH, "output": 7},
    # output differs from expected -> the err arm carrying expected-vs-got.
    {"case": {"function": "double", "input": 21, "expected": 99},
     "verdict": _MISMATCH, "expected_value": 99, "got_value": 42},
    # the absence case: the named function is not in the map -> a Fault.
    {"case": {"function": "missing_fn", "input": 1, "expected": 1},
     "verdict": _FAULT, "map": {}},
    # the could-not-run case: the function is present but the case gives the wrong
    # arity, so invoking it throws -> a Fault, never a crash of the gate.
    {"case": {"function": "double", "args": [1, 2], "expected": 0},
     "verdict": _FAULT},
]


def _is_fault(got):
    """A honest-test Fault is a dict carrying problem and remedy, not a Result."""
    return (
        isinstance(got, dict)
        and "problem" in got
        and "remedy" in got
        and "ok" not in got
        and "err" not in got
    )


def probe_evaluate_case():
    """evaluate_case builds the call from the portable case, invokes the function, and judges its output against the expected value: ok on a match, err carrying expected-vs-got on a mismatch, a Fault when a named function is absent."""
    bad = []
    for entry in _CASES:
        case = entry["case"]
        function_map = entry.get("map", _MAP)
        got = evaluate_case(case, function_map)
        label = case["function"]
        if entry["verdict"] == _MATCH:
            if got != {"ok": entry["output"]}:
                bad.append(f"evaluate_case({label}, match) -> {got}, expected {{'ok': {entry['output']!r}}}")
        elif entry["verdict"] == _MISMATCH:
            if not (isinstance(got, dict) and "err" in got and "ok" not in got):
                bad.append(f"evaluate_case({label}, mismatch) -> {got}, expected an err Result")
                continue
            detail = got["err"].get("detail", {})
            if detail.get("expected") != entry["expected_value"] or detail.get("got") != entry["got_value"]:
                bad.append(
                    f"evaluate_case({label}, mismatch) err detail {detail}, "
                    f"expected expected={entry['expected_value']!r} got={entry['got_value']!r}"
                )
        else:  # _FAULT
            if not _is_fault(got):
                bad.append(f"evaluate_case({label}, unknown) -> {got}, expected a Fault with problem and remedy")
    return bad


def run():
    bad = probe_evaluate_case()
    for line in bad:
        print(line)
    print(f"probe_evaluate_case: {len(bad)} failure(s)")
    return bad


if __name__ == "__main__":
    import sys

    sys.exit(1 if run() else 0)
