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

import json
import sys
from pathlib import Path

from honest_type import (
    VocabularyError,
    binding,
    chain,
    classify,
    composed,
    err,
    fault,
    maybe,
    merge,
    ok,
    validate_all,
    vocabulary,
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


_LINKS = {"pass": _link_pass, "set_role": _link_set_role, "fault": _link_fault, "bad": _link_bad}
_COMBINATORS = {"chain": chain, "validate_all": validate_all}


def _slot(spec):
    """A binding value from data: 'slot' or {'maybe': 'slot'}."""
    if hasattr(spec, "get") and "maybe" in spec:
        return maybe(spec["maybe"])
    return spec


def _composed(spec):
    """A composed type from data; captures is 'type' or {'maybe': 'type'}."""
    return composed(spec["name"], spec["requires"], _slot(spec["captures"]))


def _check_construction(case):
    try:
        vocabulary({name: set(members) for name, members in case["declarations"].items()})
        result, message = "ok", ""
    except VocabularyError as exc:
        result, message = "error", str(exc)
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
    if case["expect"] == "err":
        matched = "err" in result and result["err"]["code"] == case["expect_code"]
        return matched, f"got {result}"
    manifest = result.get("ok", {})
    matched = "ok" in result and all(
        manifest.get(slot) == value for slot, value in case.get("expect_manifest", {}).items()
    )
    return matched, f"got {result}"


_CHECKERS = {
    "construction": _check_construction,
    "classify": _check_classify,
    "merge": _check_merge,
    "chainrun": _check_chainrun,
}


def _kind(case):
    if "combinator" in case:
        return "chainrun"
    if "merge_a" in case:
        return "merge"
    return "classify" if "tokens" in case else "construction"


def run(suite_path):
    suite = json.loads(Path(suite_path).read_text(encoding="utf-8"))
    passed = 0
    failed = 0
    for case in suite["cases"]:
        ok, detail = _CHECKERS[_kind(case)](case)
        if ok:
            passed += 1
        else:
            failed += 1
            print(f"FAIL {case['id']} [{_kind(case)}]: {detail}")
    print(f"conformance: {passed} passed, {failed} failed, {passed + failed} total")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    default = str(Path(__file__).parent / "suite.json")
    raise SystemExit(run(sys.argv[1] if len(sys.argv) > 1 else default))
