"""Honest probe for honest-test's run_resolved_call (feature Scenario:
run_resolved_call runs one resolved call at the engine's boundary).

run_resolved_call is the value oracle's boundary: it invokes the function under
test by positional or keyword arguments, applies each resolved $call application
bottom-up first, and drives an awaitable result to completion so an async
function is checkable, returning the finished value for compare_output to judge
(.hd run_resolved_call; architecture section 8.6).

The ResolvedCall shape is declared ({function, args, kwargs, expected}), so the
positional, keyword and async cases are built by hand with a real function under
test. The $call case is built through resolve_call, the real producer of a
resolved application node, because that node's internal shape is not declared
here; run_resolved_call must apply it bottom-up and return the composed value.
"""

import asyncio

from honest_test import resolve_call, run_resolved_call


def _add(a, b):
    """A real pure function under test: it returns the sum of its two inputs."""
    return a + b


def _square(n):
    """A real pure function under test: it returns the square of its input."""
    return n * n


def _double(n):
    """A real pure function a $call names, to be applied bottom-up before the outer call."""
    return n * 2


async def _async_double(n):
    """A real async function under test: run_resolved_call must drive it to completion."""
    return n * 2


def probe_run_resolved_call():
    """run_resolved_call invokes by positional and keyword arguments, drives an
    async result to completion, and applies a $call argument bottom-up."""
    bad = []

    positional = run_resolved_call({"function": _add, "args": [2, 3], "kwargs": {}, "expected": 5})
    if positional != 5:
        bad.append(f"a positional call add(2, 3) should return 5, got {positional!r}")

    keyword = run_resolved_call({"function": _add, "args": [], "kwargs": {"a": 4, "b": 6}, "expected": 10})
    if keyword != 10:
        bad.append(f"a keyword call add(a=4, b=6) should return 10, got {keyword!r}")

    single = run_resolved_call({"function": _square, "args": [7], "kwargs": {}, "expected": 49})
    if single != 49:
        bad.append(f"a single-argument call square(7) should return 49, got {single!r}")

    awaited = run_resolved_call({"function": _async_double, "args": [21], "kwargs": {}, "expected": 42})
    if asyncio.iscoroutine(awaited):
        bad.append("an async function's result must be driven to completion, not returned as a coroutine")
    elif awaited != 42:
        bad.append(f"an async call async_double(21) should return 42 once driven to completion, got {awaited!r}")

    function_map = {"add": _add, "double": _double}
    nested = resolve_call(
        {"function": "add", "args": [{"$call": "double", "args": [5]}, 3], "expected": 13},
        function_map,
    )
    if not (isinstance(nested, dict) and "function" in nested and "problem" not in nested):
        bad.append(f"resolve_call should produce a ResolvedCall carrying a $call node, got {nested!r}")
    else:
        composed = run_resolved_call(nested)
        if composed != 13:
            bad.append(f"a $call argument should be applied bottom-up: add(double(5), 3) should return 13, got {composed!r}")

    return bad


def run():
    messages = probe_run_resolved_call()
    for message in messages:
        print(f"FAIL HT-probe [run_resolved_call]: {message}")
    passed = 0 if messages else 1
    print(f"run_resolved_call: {passed} passed, {len(messages)} failed")
    return 0 if not messages else 1


if __name__ == "__main__":
    raise SystemExit(run())
