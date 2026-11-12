"""The value oracle, scaffolding, and proof events (spec sections 8.2, 8.5, 8.6).

evaluate_case walks a portable expression against the function map and runs the function under
test; generate_scaffolding renders a honest-gherkin step module from a chain's links;
build_proof_event assembles one hf.proof.checked record. All pure (evaluate_case drives only the
injected functions).
"""

import asyncio
import inspect

from honest_type import err, fault, ok

from honest_test.support import _fault, _is_fault


def _resolve(value, function_map):
    """Resolve one portable value against the function map (spec section 8.6): a `$ref` names a
    callable resolved from the map, a `$call` applies a named function to its resolved arguments,
    and any other value is a literal (itself). Returns a Fault for an unknown name. This keeps
    suite.json pure data while letting a case reach a function-taking function by naming it, with no
    callable embedded in the data."""
    if isinstance(value, dict) and "$ref" in value:
        name = value["$ref"]
        if name not in function_map:
            return _fault(
                f"value-oracle $ref named unknown function {name!r}",
                "add the named function to the suite's function map",
            )
        return function_map[name]
    if isinstance(value, dict) and "$call" in value:
        name = value["$call"]
        if name not in function_map:
            return _fault(
                f"value-oracle $call named unknown function {name!r}",
                "add the named function to the suite's function map",
            )
        arguments = []
        for argument in (value["args"] if "args" in value else []):
            resolved = _resolve(argument, function_map)
            if _is_fault(resolved):
                return resolved
            arguments.append(resolved)
        return _run_to_completion(function_map[name](*arguments))
    if isinstance(value, list):
        resolved = []
        for element in value:
            element_value = _resolve(element, function_map)
            if _is_fault(element_value):
                return element_value
            resolved.append(element_value)
        return resolved
    return value


def _run_to_completion(result):
    """Run an awaitable result to completion so async functions are checkable (spec 8.6)."""
    if inspect.isawaitable(result):
        return asyncio.run(result)
    return result


def evaluate_case(case, function_map):
    """Run one portable value-oracle case and judge the function's output against the known-good
    value (spec section 8.6), the leg that earns a function proved. Evaluate the input expression
    to the argument, run the function under test to completion, evaluate the expected expression,
    and compare: return honest-type's ok Result carrying the output when it equals the expected
    value, honest-type's err Result carrying an expected-vs-got fault when it differs, and a
    honest-test Fault when a named function or expression is unknown. Performs no I/O of its own;
    the functions under test are injected through the map."""
    name = case["function"]
    if name not in function_map:
        return _fault(
            f"value-oracle case named unknown function {name!r}",
            "add the named function to the suite's function map",
        )
    # Build the call from the portable case: a single `input`, positional `args`, or keyword
    # `kwargs`, each entry a literal, a $ref to a callable, or a $call applying one.
    # honest: disable HC-P002: the function under test is injected arbitrary code, so a case it
    # cannot accept (wrong arity) or that throws is a case that could not run, returned as a Fault
    # so one stale case does not crash the whole value gate, never swallowed as a pass.
    try:
        if "args" in case:
            resolved = []
            for argument in case["args"]:
                value = _resolve(argument, function_map)
                if _is_fault(value):
                    return value
                resolved.append(value)
            output = _run_to_completion(function_map[name](*resolved))
        elif "kwargs" in case:
            resolved = {}
            for key, argument in case["kwargs"].items():
                value = _resolve(argument, function_map)
                if _is_fault(value):
                    return value
                resolved[key] = value
            output = _run_to_completion(function_map[name](**resolved))
        else:
            argument = _resolve(case.get("input"), function_map)
            if _is_fault(argument):
                return argument
            output = _run_to_completion(function_map[name](argument))
    except Exception as exc:
        return _fault(
            f"value-oracle case for {name!r} could not run: {exc}",
            "fix the case's arguments or the function's signature so it can be invoked",
        )
    # honest: enable HC-P002
    expected = _resolve(case["expected"], function_map)
    if _is_fault(expected):
        return expected
    if output == expected:
        return ok(output)
    return err(fault(
        "value_mismatch",
        f"{name} returned {output!r}, expected {expected!r}",
        "server",
        [],
        {"expected": expected, "got": output},
    ))


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
