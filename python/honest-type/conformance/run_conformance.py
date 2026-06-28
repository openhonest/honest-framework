"""honest-type conformance runner (sections 2, 3, 6, 9 — units 1-2).

Each case is data. Two kinds:
  - construction: {declarations, expect: ok|error, error_contains?} — vocabulary() contract.
  - classify:     {declarations, binding?, tokens, expect_manifest?, expect_rejections?,
                   expect_fault?} — classify() contract (set recognizers only; predicate /
                   insensitive / non-string cases need non-JSON inputs and are verified
                   separately).
The runner builds the objects from the data and checks; no per-case hand-coded tests.

  uv run --package honest-type python honest-type/conformance/run_conformance.py
"""

import asyncio
import json
import sys
from pathlib import Path

from honest_type import (
    StateMachineError,
    VocabularyError,
    binding,
    catch_at_boundary,
    chain,
    check_rejections,
    classify,
    composed,
    err,
    fault,
    is_link,
    link,
    link_meta,
    maybe,
    merge,
    ok,
    state_machine,
    transition,
    validate_all,
    vocabulary,
)


def _build_sm(case):
    transitions = {(t[0], t[1]): t[2] for t in case["transitions"]}
    return state_machine(
        set(case["states"]), set(case["events"]), transitions, case["initial"], case.get("terminal")
    )


def _vocab(declarations):
    return vocabulary({name: set(members) for name, members in declarations.items()})


# Link fixtures for the chain cases (section 10). Links are functions, so they cannot be
# JSON; the cases name them and the runner supplies the implementations.
def _link_pass(manifest):
    return ok(manifest)


def _link_set_role(manifest):
    return ok({**manifest, "role": "admin"})


def _link_fault(manifest):
    return err(fault("boom", "boom", "server"))


def _link_bad(manifest):
    return {"weird": 1}  # neither ok nor err -> non_result_return


def _link_unrecognized(manifest):
    return err(fault("unrecognized", "no", "client"))


def _link_client_fault(manifest):
    # A client-category fault whose code is NOT in _FAULT_TO_OUTPUT, so the boundary routes it by
    # category default (client) — exercising the "client" arm of the category table.
    return err(fault("denied", "no", "client"))


def _link_raise(manifest):
    raise ValueError("kaboom")


@link(boundary=True, accepts="user_vocab")
def _declared_link(manifest):
    return ok({**manifest, "role": "admin"})


# Async links (section 10.6): a chain or validate_all containing any of these is itself async.
async def _link_async(manifest):
    return ok({**manifest, "async_ran": "yes"})


async def _link_async_fault(manifest):
    return err(fault("async_boom", "async link failed", "client"))


async def _link_async_bad(manifest):
    return {"weird": 1}  # neither ok nor err -> non_result_return, after await


_LINKS = {
    "async": _link_async,
    "async_fault": _link_async_fault,
    "async_bad": _link_async_bad,
    "pass": _link_pass,
    "set_role": _link_set_role,
    "fault": _link_fault,
    "bad": _link_bad,
    "unrecognized": _link_unrecognized,
    "client_fault": _link_client_fault,
    "raise": _link_raise,
    "declared": _declared_link,
}
_COMBINATORS = {"chain": chain, "validate_all": validate_all}


# Boundary output fixtures (section 11.4): output functions, not status codes.
def _out_success(manifest):
    return {"status": 200, "body": manifest}


def _out_server(failure):
    return {"status": 500, "code": failure["code"]}


def _out_client(failure):
    return {"status": 400, "code": failure["code"]}


_FAULT_TO_OUTPUT = {"unrecognized": lambda failure: {"status": 422, "code": failure["code"]}}


def _slot(spec):
    """A binding value from data: 'slot' or {'maybe': 'slot'}."""
    if hasattr(spec, "get") and "maybe" in spec:
        return maybe(spec["maybe"])
    return spec


def _composed(spec):
    """A composed type from data; captures is 'type' or {'maybe': 'type'}."""
    return composed(spec["name"], spec["requires"], _slot(spec["captures"]))


def _check_construction(case):
    caught = None
    try:
        vocabulary({name: set(members) for name, members in case["declarations"].items()})
        result, message = "ok", ""
    except VocabularyError as exc:
        result, message, caught = "error", str(exc), exc
    if "expect_fault" in case:
        got = getattr(caught, "fault", None) or {}
        expected = case["expect_fault"]
        ok = all(got.get(field) == value for field, value in expected.items())
        return ok, f"got {result} fault={getattr(caught, 'fault', None)}"
    ok = result == case["expect"] and case.get("error_contains", "") in message
    return ok, f"got {result} ({message[:50]})"


def _check_classify(case):
    composed_types = [_composed(spec) for spec in case.get("composed_types", [])]
    vocab = vocabulary(
        {name: set(members) for name, members in case["declarations"].items()},
        composed_types=composed_types,
    )
    bind = binding({k: _slot(v) for k, v in case["binding"].items()}) if "binding" in case else None
    result = classify(case["tokens"], vocab, bind)
    if "expect_fault" in case:
        ok = "err" in result and result["err"]["code"] == case["expect_fault"]
        return ok, f"got {result}"
    reasons = [r["reason"] for r in result.get("_rejections", [])]
    # `slot in result` distinguishes Nothing (present, null) from an absent slot.
    manifest_ok = all(
        slot in result and result.get(slot) == value
        for slot, value in case.get("expect_manifest", {}).items()
    )
    rejections_ok = all(reason in reasons for reason in case.get("expect_rejections", []))
    return manifest_ok and rejections_ok, f"got {result}"


def _check_merge(case):
    try:
        merge(_vocab(case["merge_a"]), _vocab(case["merge_b"]))
        result, message = "ok", ""
    except VocabularyError as exc:
        result, message = "error", str(exc)
    ok = result == case["expect"] and case.get("error_contains", "") in message
    return ok, f"got {result} ({message[:50]})"


def _check_chainrun(case):
    links = [_LINKS[name] for name in case["links"]]
    result = _COMBINATORS[case["combinator"]](*links)(case["initial"])
    if asyncio.iscoroutine(result):
        result = asyncio.run(result)
    if case["expect"] == "err":
        failure = result.get("err", {})
        matched = "err" in result and failure.get("code") == case["expect_code"]
        for field in ("input", "results", "link"):
            if case.get(f"expect_fault_{field}") and field not in failure:
                matched = False
        return matched, f"got {result}"
    manifest = result.get("ok", {})
    matched = "ok" in result and all(
        manifest.get(slot) == value for slot, value in case.get("expect_manifest", {}).items()
    )
    return matched, f"got {result}"


def _check_boundary(case):
    handler = chain(*[_LINKS[name] for name in case["links"]])
    wrapped = catch_at_boundary(
        handler, _FAULT_TO_OUTPUT, _out_success, _out_server, _out_client
    )
    result = wrapped(case["initial"])
    status_ok = result["status"] == case["expect_status"]
    code_ok = "expect_code" not in case or result.get("code") == case["expect_code"]
    return status_ok and code_ok, f"got {result}"


def _check_rejections(case):
    result = check_rejections(case["rejection_manifest"])
    if case["expect"] == "err":
        failure = result.get("err", {})
        matched = "err" in result and failure.get("code") == case["expect_code"]
        for field in ("category", "message", "detail"):
            key = f"expect_{field}"
            if key in case:
                matched = matched and failure.get(field) == case[key]
        return matched, f"got {result}"
    matched = "ok" in result and "_rejections" not in result["ok"]
    return matched, f"got {result}"


def _check_linkmeta(case):
    fn = _LINKS[case["link"]]
    meta = link_meta(fn)
    matched = is_link(fn) and callable(fn)
    for field in ("boundary", "name", "accepts"):
        key = f"expect_{field}"
        if key in case:
            matched = matched and meta.get(field) == case[key]
    return matched, f"got {meta}"


def _check_statemachine(case):
    if "apply" in case:
        machine = _build_sm(case)
        state, event = case["apply"]
        result = transition(machine, state, event)
        if "expect_state" in case:
            return "ok" in result and result["ok"]["state"] == case["expect_state"], f"got {result}"
        return "err" in result and result["err"]["code"] == case["expect_code"], f"got {result}"
    try:
        _build_sm(case)
        outcome, message = "ok", ""
    except StateMachineError as exc:
        outcome, message = "error", str(exc)
    ok_ = outcome == case["expect"] and case.get("error_contains", "") in message
    return ok_, f"got {outcome} ({message[:40]})"


def _check_value(case):
    """A value-oracle case: call a named function with literal args and confirm its exact output. Pins
    the constructor/predicate results (the shapes of fault, rejection, ok/err, and the bounded predicate)
    that the behavioural checkers only exercise indirectly. `module` defaults to the package."""
    import importlib

    module = importlib.import_module(case.get("module", "honest_type"))
    fn = getattr(module, case["call"])
    got = fn(*case.get("args", []), **case.get("kwargs", {}))
    return got == case["expect"], f"got {got!r}"


_CHECKERS = {
    "construction": _check_construction,
    "classify": _check_classify,
    "merge": _check_merge,
    "chainrun": _check_chainrun,
    "boundary": _check_boundary,
    "rejections": _check_rejections,
    "linkmeta": _check_linkmeta,
    "statemachine": _check_statemachine,
    "value": _check_value,
}


def _kind(case):
    if "call" in case:
        return "value"
    if "sm" in case:
        return "statemachine"
    if "link" in case:
        return "linkmeta"
    if "expect_status" in case:
        return "boundary"
    if "rejection_manifest" in case:
        return "rejections"
    if "combinator" in case:
        return "chainrun"
    if "merge_a" in case:
        return "merge"
    return "classify" if "tokens" in case else "construction"


import honest_type as _ht


@_ht.link()
def value_link(manifest):
    return _ht.ok({**manifest, "seen": True})


def _make_machine(states, events, transitions, initial):
    return _ht.state_machine(set(states), set(events), {(t[0], t[1]): t[2] for t in transitions}, initial)


# The value-oracle function map: the public functions, plus fixtures a value case may $ref/$call —
# a sample link (for is_link/link_meta/execute_chain) and a JSON-able machine builder (for transition,
# whose tuple-keyed transitions dict cannot be carried directly). proof_run and value-check.py read it.
_VALUE_FUNCTIONS = {
    **{name: getattr(_ht, name) for name in _ht.__all__ if callable(getattr(_ht, name))},
    "value_link": value_link,
    "make_machine": _make_machine,
}


def run(suite_path):
    suite = json.loads(Path(suite_path).read_text(encoding="utf-8"))
    passed = 0
    failed = 0
    for case in suite["cases"]:
        if "value_case" in case:
            continue  # value cases are checked centrally by value-check.py; a module cannot run the oracle on itself
        ok, detail = _CHECKERS[_kind(case)](case)
        if ok:
            passed += 1
        else:
            failed += 1
            print(f"FAIL {case['id']} [{_kind(case)}]: {detail}")
    print(f"conformance: {passed} passed, {failed} failed, {passed + failed} total")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    import laws_ht

    default = str(Path(__file__).parent / "suite.json")
    suite_status = run(sys.argv[1] if len(sys.argv) > 1 else default)
    laws_status = laws_ht.run()
    raise SystemExit(suite_status or laws_status)
