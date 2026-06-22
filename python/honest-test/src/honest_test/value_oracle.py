"""The value-assertion oracle (section 8.6): the value half of "proved".

Auto-generation (sections 3-4) proves a function's *properties* (purity, idempotency) and its
output *shape*, but never its *value* — it generates inputs and cannot know the correct output. The
value oracle supplies exactly that missing piece: the known-good (input, expected) pairs a function's
output is compared against. Those pairs are the module's portable contract — the suite.json cases —
so the values are pinned once, not authored twice.

The oracle runs on honest-gherkin's execution model: each case is a three-step scenario (supply the
input, call the function, assert the oracle) folded over an immutable context, so a wrong value is a
failed `Then` recorded as assertion_failed, an unknown or raising function is step_errored, and a
malformed case is rejected — all as data, never a crash. Concrete input/expected are bound directly
from the case (they are already structured data), so a list or dict value crosses in intact, where a
text capture could not. A function earns `proved` only when every one of its value cases holds
(section 8.5), alongside the honesty checks and full coverage.
"""

from honest_gherkin import empty_registry, register_step, run_scenario


def _oracle_expected(case, result):
    """`Then it returns {expected}` — the result equals the known-good value (section 8.6)."""
    assert result == case["expected"], f"expected {case['expected']!r}, got {result!r}"


def _oracle_fault(case, result):
    """`Then it returns a fault with code {code}` — the result is an err with that code."""
    assert "err" in result and result["err"]["code"] == case["fault"], f"expected fault {case['fault']!r}, got {result!r}"


def _oracle_ok(case, result):
    """`Then the result is ok` — the result is an ok Result (section 8.6)."""
    assert "ok" in result, f"expected an ok result, got {result!r}"


def _oracle_field(case, result):
    """`Then the field "{name}" of the result is {value}` — one named field equals a known value."""
    field = case["field"]
    assert result[field["name"]] == field["value"], f"expected field {field['name']!r} == {field['value']!r}, got {result!r}"


# Which `Then` an oracle case carries is named by the key it declares; this is the reusable handler
# set (section 8.6), dispatched as a table rather than an if/elif chain.
_ORACLE_ASSERTIONS = {
    "expected": _oracle_expected,
    "fault": _oracle_fault,
    "ok": _oracle_ok,
    "field": _oracle_field,
}


def _oracle_kind(case):
    """The oracle a case declares: the first recognised oracle key it carries, or "" if none."""
    for kind in _ORACLE_ASSERTIONS:
        if kind in case:
            return kind
    return ""


def check_oracle(case, result):
    """Run a case's value oracle against a function result (section 8.6). Raises AssertionError on a
    mismatch or a case that declares no oracle; honest-gherkin catches it and records the fault."""
    kind = _oracle_kind(case)
    assert kind, f"value case declares no oracle (one of {list(_ORACLE_ASSERTIONS)}): {case}"
    _ORACLE_ASSERTIONS[kind](case, result)


def _bound_registry(case, functions):
    """A per-case registry whose three steps bind the case's concrete data directly (section 8.6):
    supply the input, call the named function on it, and assert the oracle. The function is resolved
    inside the step so an unknown name surfaces as a caught fault, not a registration-time crash."""
    def given(context):
        return {**context, "input": case["input"]}

    def when(context):
        return {**context, "result": functions[case["function"]](context["input"])}

    def then(context):
        check_oracle(case, context["result"])
        return context

    registry = empty_registry()
    registry = register_step(registry, "given", "the input is supplied", given)
    registry = register_step(registry, "when", "the function is called", when)
    registry = register_step(registry, "then", "the value oracle holds", then)
    return registry


_VALUE_SCENARIO = {
    "name": "value oracle",
    "steps": [
        {"kind": "given", "resolved_kind": "given", "text": "the input is supplied", "source_line": 0},
        {"kind": "when", "resolved_kind": "when", "text": "the function is called", "source_line": 0},
        {"kind": "then", "resolved_kind": "then", "text": "the value oracle holds", "source_line": 0},
    ],
    "tags": [],
    "source_line": 0,
}


def run_value_case(case, functions):
    """Run one value-oracle case through honest-gherkin (section 8.6). Returns {id, proved, fault}:
    proved iff every step is ok, else the first fault (assertion_failed for a wrong value,
    step_errored for an unknown or raising function)."""
    report = run_scenario(_VALUE_SCENARIO, [], _bound_registry(case, functions))
    faults = [step["fault"] for step in report["step_results"] if step["fault"] is not None]
    return {"id": case.get("id", ""), "proved": report["status"] == "ok", "fault": faults[0] if faults else None}


def run_value_cases(cases, functions):
    """Run every value-oracle case against the function map (section 8.6): the executable face of the
    suite.json value contract."""
    return [run_value_case(case, functions) for case in cases]
