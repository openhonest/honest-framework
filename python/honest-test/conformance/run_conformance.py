"""honest-test conformance runner (sections 3.2, 3.5 - unit 1).

Each case is data. Two kinds:
  - enumeration: {declarations, maybe?, expect_count, expect_contains?} - enumerate_sets()
    builds the cartesian product of the declared Sets (maybe types add Nothing/null).
  - adversarial: {value, expect_contains?, expect_excludes?, expect_count_min?} -
    adversarial_neighbors() generates the neighbour classes for one value.
The runner builds the objects from the data and calls the generators; no per-case tests.

  uv run --package honest-test python honest-test/conformance/run_conformance.py
"""

import json
import sys
import tomllib
from pathlib import Path

from honest_type import binding, maybe, vocabulary

from honest_test import (
    adversarial_neighbors,
    classify_source,
    enumerate_lengths,
    enumerate_sets,
    numeric_values,
    supplied_for,
)


def _vocab(declarations):
    return vocabulary({name: set(members) for name, members in declarations.items()})


def _check_enumeration(case):
    vocab = _vocab(case["declarations"])
    bind = None
    if "maybe" in case:
        bind = binding(
            {name: (maybe(name) if name in case["maybe"] else name) for name in case["declarations"]}
        )
    produced = enumerate_sets(vocab, bind)
    ok = len(produced) == case["expect_count"]
    for want in case.get("expect_contains", []):
        ok = ok and want in produced
    return ok, f"got {len(produced)} cases"


def _check_adversarial(case):
    neighbours = set(adversarial_neighbors(case["value"]))
    ok = True
    for want in case.get("expect_contains", []):
        ok = ok and want in neighbours
    for unwanted in case.get("expect_excludes", []):
        ok = ok and unwanted not in neighbours
    if "expect_count_min" in case:
        ok = ok and len(neighbours) >= case["expect_count_min"]
    return ok, f"got {len(neighbours)} neighbours"


def _check_predicate(case):
    codebase = set(case["codebase"]) if "codebase" in case else None
    got = classify_source(case["source"], codebase)
    return got == case["expect_class"], f"got {got}"


def _check_numeric(case):
    kwargs = {key: case[key] for key in ("limit", "negative", "as_float") if key in case}
    values = numeric_values(**kwargs)
    if "expect_values" in case:
        return values == case["expect_values"], f"got {values}"
    ok = all(want in values for want in case.get("expect_contains", []))
    ok = ok and len(values) >= case.get("expect_count_min", 0)
    return ok, f"got {len(values)} values"


def _check_length(case):
    result = enumerate_lengths(case["source"])
    valid_lengths = sorted(len(s) for s in result["valid"])
    invalid_lengths = sorted(len(s) for s in result["invalid"])
    ok = result["min"] == case["expect_min"] and result["max"] == case["expect_max"]
    if "expect_valid_lengths" in case:
        ok = ok and valid_lengths == sorted(case["expect_valid_lengths"])
    if "expect_invalid_lengths" in case:
        ok = ok and invalid_lengths == sorted(case["expect_invalid_lengths"])
    return ok, f"got min={result['min']} max={result['max']} valid={valid_lengths} invalid={invalid_lengths}"


def _check_supplied(case):
    config = tomllib.loads(case["toml"]) if "toml" in case else case.get("config", {})
    result = supplied_for(config, case["predicate"])
    if case.get("expect_none"):
        return result is None, f"got {result}"
    ok = result is not None
    for field in ("valid", "invalid", "strategy"):
        key = f"expect_{field}"
        if key in case:
            ok = ok and result[field] == case[key]
    return ok, f"got {result}"


_CHECKERS = {
    "enumeration": _check_enumeration,
    "adversarial": _check_adversarial,
    "predicate": _check_predicate,
    "numeric": _check_numeric,
    "length": _check_length,
    "supplied": _check_supplied,
}


def _kind(case):
    if "predicate" in case:
        return "supplied"
    if case.get("gen") in ("numeric", "length"):
        return case["gen"]
    if "expect_class" in case:
        return "predicate"
    return "adversarial" if "value" in case else "enumeration"


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
