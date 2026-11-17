"""The value-oracle engine (spec section 8.6): a sibling module's conformance runner
enters evaluate_case to run one portable suite case and compare the function's output
against the known-good value. resolve_call is pure (reads the map, runs nothing);
run_resolved_call is the one boundary that runs the injected function under test;
compare_output is the pure verdict.
"""

import asyncio

from honest_type import err, fault, ok

from honest_test._util import _choose, _pick, _read_or

_MISSING = object()
_value_kind = lambda value: _choose(hasattr(value, "get") and "$ref" in value, "ref", _choose(hasattr(value, "get") and "$call" in value, "call", _choose(hasattr(value, "get"), "mapping", _choose(hasattr(value, "append"), "list", "scalar"))))


def resolve_call(case, function_map):
    """Resolve one suite case against the function map into a runnable ResolvedCall (section
    8.6): a literal is itself, a $ref is looked up to its callable, and a $call becomes a
    resolved application node carrying its looked-up callable and its own resolved
    arguments. Returns a honest-test Fault when any name is not in the map. It runs no
    code: resolution only reads the map."""
    faults = []

    def _lookup(name):
        found = _read_or(function_map, name, _MISSING)
        return _pick(
            found is _MISSING,
            lambda: _record_fault(name),
            lambda: found,
        )

    def _record_fault(name):
        trouble = {
            "problem": f"the value-oracle case named {name!r}, which the function map does not hold",
            "remedy": f"add {name!r} to the suite's function map so the oracle can resolve it",
        }
        faults.append(trouble)
        return trouble

    def _resolve(value):
        handlers = {
            "scalar": lambda v: v,
            "list": lambda v: [_resolve(element) for element in v],
            "mapping": lambda v: {key: _resolve(inner) for key, inner in v.items()},
            "ref": lambda v: _lookup(v["$ref"]),
            "call": lambda v: {"$call": _lookup(v["$call"]), "args": [_resolve(argument) for argument in v["args"]]},
        }
        return handlers[_value_kind(value)](value)

    def _resolve_args():
        return _pick(
            "args" in case,
            lambda: [_resolve(argument) for argument in case["args"]],
            lambda: _pick("input" in case, lambda: [_resolve(case["input"])], lambda: []),
        )

    function = _lookup(case["function"])
    args = _resolve_args()
    kwargs = {name: _resolve(value) for name, value in _read_or(case, "kwargs", {}).items()}
    expected = _resolve(case["expected"])
    return _pick(
        len(faults) > 0,
        lambda: faults[0],
        lambda: {"function": function, "args": args, "kwargs": kwargs, "expected": expected},
    )


def run_resolved_call(resolved):
    """Run one resolved value-oracle call at the engine's boundary (section 8.6): apply each
    $call application bottom-up, invoke the function under test by positional or keyword
    arguments, and drive an awaitable result to completion so an async function is
    checkable, returning the finished value."""
    def _drive(result):
        return _pick(asyncio.iscoroutine(result), lambda: asyncio.run(result), lambda: result)

    def _apply(value):
        is_call = hasattr(value, "get") and "$call" in value
        return _pick(is_call, lambda: _drive(value["$call"](*[_apply(argument) for argument in value["args"]])), lambda: value)

    args = [_apply(argument) for argument in resolved["args"]]
    kwargs = {name: _apply(value) for name, value in resolved["kwargs"].items()}
    return _drive(resolved["function"](*args, **kwargs))


def compare_output(output, expected):
    """Judge one value-oracle output against the known-good value (section 8.6): ok carrying
    the output when it equals the expected value, err carrying an expected-vs-got fault when
    they differ. The output is compared whole."""
    return _pick(
        output == expected,
        lambda: ok(output),
        lambda: err(fault("value_mismatch", f"expected {expected!r}, got {output!r}", "server", [], {"expected": expected, "got": output})),
    )


def run_case(case, function_map):
    """Drive the value-oracle sequence for one case (section 8.6): resolve it, pass a
    resolution Fault outward and run nothing, otherwise run the resolved call at the
    boundary and judge the output against the resolved expected value."""
    resolved = resolve_call(case, function_map)
    is_fault = hasattr(resolved, "get") and "problem" in resolved
    return _pick(
        is_fault,
        lambda: resolved,
        lambda: compare_output(run_resolved_call(resolved), resolved["expected"]),
    )


def evaluate_case(case, function_map):
    """The value-oracle door (section 8.6): hand the case and the function map to run_case
    and return what it returned — an ok Result, an err Result, or a honest-test Fault."""
    return run_case(case, function_map)
