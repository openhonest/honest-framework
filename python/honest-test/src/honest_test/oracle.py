"""The value oracle, scaffolding, and proof events (spec sections 8.2, 8.5, 8.6).

evaluate_case walks a portable expression against the function map and runs the function under
test; generate_scaffolding renders a honest-gherkin step module from a chain's links;
build_proof_event assembles one hf.proof.checked record. All pure (evaluate_case drives only the
injected functions).
"""

import asyncio
import inspect
from functools import reduce

from honest_type import fault

from honest_test._util import _pick, _read_or
from honest_test.support import _fault, _is_fault


def _run_to_completion(result):
    """Run an awaitable result to completion so async functions are checkable (spec 8.6)."""
    return _pick(inspect.isawaitable(result), lambda: asyncio.run(result), lambda: result)


def _resolve_literal(value, function_map):
    """A value that is neither a $ref, a $call nor a list resolves to itself (spec section 8.6)."""
    return value


def _resolve_ref(value, function_map):
    """A `$ref` names a callable resolved from the function map (spec section 8.6), or a Fault for
    an unknown name."""
    name = value["$ref"]
    return _pick(
        name in function_map,
        lambda: function_map[name],
        lambda: _fault(
            f"value-oracle $ref named unknown function {name!r}",
            "add the named function to the suite's function map",
        ),
    )


def _resolve_call_known(value, function_map, name):
    """Apply a known `$call` function to its resolved arguments (spec section 8.6); a faulting
    argument short-circuits to that Fault."""
    resolved = _resolve_each(_read_or(value, "args", []), function_map)
    return _pick(
        _is_fault(resolved),
        lambda: resolved,
        lambda: _run_to_completion(function_map[name](*resolved)),
    )


def _resolve_call(value, function_map):
    """A `$call` applies a named function to its resolved arguments (spec section 8.6), or a Fault
    for an unknown name."""
    name = value["$call"]
    return _pick(
        name in function_map,
        lambda: _resolve_call_known(value, function_map, name),
        lambda: _fault(
            f"value-oracle $call named unknown function {name!r}",
            "add the named function to the suite's function map",
        ),
    )


def _resolve_list(value, function_map):
    """A list resolves each element (spec section 8.6); a faulting element short-circuits to that
    Fault."""
    return _resolve_each(value, function_map)


def _classify_value(value):
    """Name the portable-value shape (spec section 8.6): ref, call, list, or literal, in that
    priority order."""
    checks = (
        (lambda v: isinstance(v, dict) and "$ref" in v, "ref"),
        (lambda v: isinstance(v, dict) and "$call" in v, "call"),
        (lambda v: isinstance(v, list), "list"),
    )
    matched = next(filter(lambda ck: ck[0](value), checks), None)
    return _pick(matched is None, lambda: "literal", lambda: matched[1])


_RESOLVERS = {
    "ref": _resolve_ref,
    "call": _resolve_call,
    "list": _resolve_list,
    "literal": _resolve_literal,
}


def _resolve(value, function_map):
    """Resolve one portable value against the function map (spec section 8.6): a `$ref` names a
    callable resolved from the map, a `$call` applies a named function to its resolved arguments,
    and any other value is a literal (itself). Returns a Fault for an unknown name. This keeps
    suite.json pure data while letting a case reach a function-taking function by naming it, with no
    callable embedded in the data."""
    handler = _read_or(_RESOLVERS, _classify_value(value), _resolve_literal)
    return handler(value, function_map)


def _resolve_each(items, function_map):
    """Resolve each element of a sequence, short-circuiting on the first Fault (spec section 8.6);
    returns the resolved list or that Fault."""
    def add(state, item):
        value = _resolve(item, function_map)
        return _pick(
            _is_fault(value),
            lambda: {"fault": value},
            lambda: {"items": state["items"] + [value]},
        )

    def step(state, item):
        return _pick("fault" in state, lambda: state, lambda: add(state, item))

    final = reduce(step, items, {"items": []})
    return _pick("fault" in final, lambda: final["fault"], lambda: final["items"])


def _resolve_each_kv(kwargs, function_map):
    """Resolve each keyword argument, short-circuiting on the first Fault (spec section 8.6);
    returns the resolved map or that Fault."""
    def add(state, kv):
        key, argument = kv
        value = _resolve(argument, function_map)
        return _pick(
            _is_fault(value),
            lambda: {"fault": value},
            lambda: {"items": {**state["items"], key: value}},
        )

    def step(state, kv):
        return _pick("fault" in state, lambda: state, lambda: add(state, kv))

    final = reduce(step, kwargs.items(), {"items": {}})
    return _pick("fault" in final, lambda: final["fault"], lambda: final["items"])


def _invoke_args(case, function_map, name):
    """Run the function with positional args resolved from the case (spec section 8.6); a halt
    carries a resolution Fault, an output carries the function's return."""
    resolved = _resolve_each(case["args"], function_map)
    return _pick(
        _is_fault(resolved),
        lambda: {"halt": resolved},
        lambda: {"output": _run_to_completion(function_map[name](*resolved))},
    )


def _invoke_kwargs(case, function_map, name):
    """Run the function with keyword args resolved from the case (spec section 8.6); a halt carries
    a resolution Fault, an output carries the function's return."""
    resolved = _resolve_each_kv(case["kwargs"], function_map)
    return _pick(
        _is_fault(resolved),
        lambda: {"halt": resolved},
        lambda: {"output": _run_to_completion(function_map[name](**resolved))},
    )


def _invoke_input(case, function_map, name):
    """Run the function with the single resolved input from the case (spec section 8.6); a halt
    carries a resolution Fault, an output carries the function's return."""
    argument = _resolve(case.get("input"), function_map)
    return _pick(
        _is_fault(argument),
        lambda: {"halt": argument},
        lambda: {"output": _run_to_completion(function_map[name](argument))},
    )


_CASE_INVOKERS = {
    "args": _invoke_args,
    "kwargs": _invoke_kwargs,
    "input": _invoke_input,
}


def _case_kind(case):
    """Name which call shape the portable case carries (spec section 8.6): args, kwargs, or the
    single input."""
    return _pick(
        "args" in case,
        lambda: "args",
        lambda: _pick("kwargs" in case, lambda: "kwargs", lambda: "input"),
    )


def _invoke_case(case, function_map, name):
    """Build and run the call from the portable case (spec section 8.6): positional args, keyword
    kwargs, or a single input, each entry a literal, a $ref to a callable, or a $call applying one."""
    invoker = _read_or(_CASE_INVOKERS, _case_kind(case), _invoke_input)
    return invoker(case, function_map, name)


def _run_case(case, function_map, name):
    """Run the case's call to an outcome (spec section 8.6): the function under test is injected
    arbitrary code, so a case it cannot accept or that throws becomes a halt Fault, never a pass."""
    try:  # honest: ignore HC-P002: the function under test is injected arbitrary code, so a case it cannot accept (wrong arity) or that throws is returned as a Fault so one stale case does not crash the whole value gate, never swallowed as a pass
        return _invoke_case(case, function_map, name)
    except Exception as exc:
        return {"halt": _fault(
            f"value-oracle case for {name!r} could not run: {exc}",
            "fix the case's arguments or the function's signature so it can be invoked",
        )}


def _compare(name, output, expected):
    """Judge the function's output against the known-good value (spec section 8.6): the output bare
    when they are equal, a bare honest-type value_mismatch Fault when they differ."""
    return _pick(
        output == expected,
        lambda: output,
        lambda: fault(
            "value_mismatch",
            f"{name} returned {output!r}, expected {expected!r}",
            "server",
            [],
            {"expected": expected, "got": output},
        ),
    )


def _judge(case, function_map, name, output):
    """Resolve the expected expression and compare it to the output (spec section 8.6); a faulting
    expected expression short-circuits to that Fault."""
    expected = _resolve(case["expected"], function_map)
    return _pick(_is_fault(expected), lambda: expected, lambda: _compare(name, output, expected))


def _evaluate_known(case, function_map, name):
    """Run and judge a case whose function the map knows (spec section 8.6): a halt Fault from the
    run short-circuits, else the output is judged against the expected value."""
    outcome = _run_case(case, function_map, name)
    return _pick(
        "halt" in outcome,
        lambda: outcome["halt"],
        lambda: _judge(case, function_map, name, outcome["output"]),
    )


def evaluate_case(case, function_map):
    """Run one portable value-oracle case and judge the function's output against the known-good
    value (spec section 8.6), the leg that earns a function proved. Evaluate the input expression
    to the argument, run the function under test to completion, evaluate the expected expression,
    and compare: return the output bare when it equals the expected value (a non-fault by is_fault),
    a bare honest-type Fault carrying an expected-vs-got detail when it differs, and a honest-test
    Fault when a named function or expression is unknown. The result is a bare union, no ok/err
    envelope (honest-type sections 12.1, 12.3). Performs no I/O of its own;
    the functions under test are injected through the map."""
    name = case["function"]
    return _pick(
        name not in function_map,
        lambda: _fault(
            f"value-oracle case named unknown function {name!r}",
            "add the named function to the suite's function map",
        ),
        lambda: _evaluate_known(case, function_map, name),
    )


def generate_scaffolding(chain_name, links):
    """Generate the Gherkin step scaffolding for a chain from its link declarations (spec section
    8.2): plain-function handlers taking the immutable context and returning a new context, wired
    through register(registry) that returns the registry. Reads no world, returns the source."""
    lines = [
        "# auto-generated scaffolding — do not edit",
        f"# chain: {chain_name}",
        "",
    ]
    for link in links:
        name = link["name"]
        lines.append(f"def step_{name}(ctx):")
        lines.append(f"    return {{**ctx, {name!r}: ctx}}")
        lines.append("")
    lines.append("def register(registry):")
    for link in links:
        name = link["name"]
        lines.append(f"    registry = register_step(registry, 'when', r'the {name} step runs', step_{name})")
    lines.append("    return registry")
    lines.append("")
    return "\n".join(lines)


def build_proof_event(function_name, scenario, cases_run, outcome, line_coverage, branch_coverage):
    """Build one hf.proof.checked event for a function honest-test proved (spec section 8.5), for
    the host runner to emit through an injected honest-observe runtime. Reads no world."""
    return {
        "function_name": function_name,
        "scenario": scenario,
        "cases_run": cases_run,
        "outcome": outcome,
        "line_coverage": line_coverage,
        "branch_coverage": branch_coverage,
    }
