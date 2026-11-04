"""Conformance fragment for the evaluate_case scenario (honest-test.feature).

Scenario: evaluate_case runs one portable value-oracle case and compares the
  output against the known-good value.
  Then it walks the input expression bottom-up — a literal is itself, a list
  evaluates its elements, a reference resolves a callable, a call applies a named
  function to its evaluated arguments — invokes the function under test, runs an
  awaitable result to completion, and returns the function's Result.
  And function_map maps each name a reference or call expression can hold to its
  callable, so a function that takes another function is reachable by naming its
  argument with no callable embedded in the data.
  And it returns a Fault when an expression names a function the map does not hold.
  And it performs no I/O of its own; the functions under test are injected.

Cases are data; one pure probe feeds them to the real honest_test.evaluate_case
and returns a list of failure strings (empty when every case holds). No classes,
no mocks: the functions in function_map are ordinary pure functions passed as
data (a real test input, not a stand-in), and the probe calls the real
honest_type.ok / err / fault to build the Result it compares against.

This is its own fragment file so the other scenarios' fragments never collide
with it. run_conformance.py / laws_htest.py are untouched.

Result is honest-type's Result: an ok arm {"ok": value} or an err arm
{"err": fault} (honest-type/src/honest_type/types.py, def ok / def err). The
Fault path is honest-test's own Fault record {problem, remedy} (honest-test.hd,
type Fault), a different shape from a Result.
"""

from honest_type import err, fault, ok

from honest_test import evaluate_case


# ---- Expression constructors (section 8.6 grammar; a plain dict per the .hd) ----
def _lit(value):
    return {"kind": "literal", "literal": value, "elements": [], "name": "", "args": []}


def _ref(name):
    return {"kind": "reference", "literal": None, "elements": [], "name": name, "args": []}


def _call(name, args):
    return {"kind": "call", "literal": None, "elements": [], "name": name, "args": args}


# ---- Functions under test: real pure functions injected through the map ----
def _wrap_ok(n):
    """A function under test that returns its argument in the ok arm."""
    return ok(n)


def _add(a, b):
    """A plain helper a call-expression applies while building the argument."""
    return a + b


def _double(n):
    """A plain callable a reference-expression resolves and hands on as data."""
    return n * 2


def _apply_to_five(f):
    """A function-taking function: it calls the callable it was handed on 5."""
    return ok(f(5))


_FAULT = fault("value_oracle", "boom", "server", [], {})


def _always_err(n):
    """A function under test that returns the err arm."""
    return err(_FAULT)


_FAULT_EXPECTED = object()  # sentinel: expect a honest-test Fault, not a Result

_CASES = [
    # literal input, ok-returning function -> the function's ok Result, verbatim.
    {
        "given": {
            "case": {"function": "wrap_ok", "input": _lit(42), "expected": _lit(42)},
            "function_map": {"wrap_ok": _wrap_ok},
        },
        "expect": {"ok": 42},
    },
    # call input: add(2, 3) is evaluated bottom-up to 5, then wrap_ok(5) -> ok(5).
    {
        "given": {
            "case": {
                "function": "wrap_ok",
                "input": _call("add", [_lit(2), _lit(3)]),
                "expected": _lit(5),
            },
            "function_map": {"wrap_ok": _wrap_ok, "add": _add},
        },
        "expect": {"ok": 5},
    },
    # reference input: "double" resolves to a callable from the map and is handed
    # to the function-taking function under test. apply_to_five(double) -> ok(10).
    {
        "given": {
            "case": {
                "function": "apply_to_five",
                "input": _ref("double"),
                "expected": _lit(10),
            },
            "function_map": {"apply_to_five": _apply_to_five, "double": _double},
        },
        "expect": {"ok": 10},
    },
    # err-returning function under test -> evaluate_case returns that err Result.
    {
        "given": {
            "case": {"function": "always_err", "input": _lit(1), "expected": _lit(1)},
            "function_map": {"always_err": _always_err},
        },
        "expect": {"err": _FAULT},
    },
    # the absence case: the named function under test is not in the map -> a Fault.
    {
        "given": {
            "case": {"function": "missing_fn", "input": _lit(1), "expected": _lit(1)},
            "function_map": {},
        },
        "expect": _FAULT_EXPECTED,
    },
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
    """evaluate_case walks the input expression bottom-up, invokes the function under test, and returns its Result — or a Fault when a named function is absent."""
    bad = []
    for case in _CASES:
        got = evaluate_case(case["given"]["case"], case["given"]["function_map"])
        expect = case["expect"]
        if expect is _FAULT_EXPECTED:
            if not _is_fault(got):
                bad.append(
                    f"evaluate_case({case['given']['case']}) -> {got}, "
                    f"expected a Fault with problem and remedy fields"
                )
            continue
        if got != expect:
            bad.append(
                f"evaluate_case({case['given']['case']}) -> {got}, expected {expect}"
            )
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
