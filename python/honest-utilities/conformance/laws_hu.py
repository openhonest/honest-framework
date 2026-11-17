"""honest-utilities conformance: the generative proof (the behavioural circle).

What the data suite in suite.json cannot easily express: the law runner's
aggregate LawRun arithmetic, resolve_env's three per-declaration cases and its
one-fault aggregation, read_env's environment boundary, and the key-redaction
guarantee. Each probe returns a list of failure strings; run() aggregates.

No classes, no mocks. Every check predicate handed to a law is a real pure
function defined here, used as test input, not a stand-in. Every declaration is a
real EnvRequest dict. Every function called is the real honest_utilities function,
and a fault is recognized by its own shape (it carries a "code").
"""

import os

from honest_utilities import (
    NOTHING,
    law,
    read_env,
    resolve_env,
    verify_laws,
)


def _is_fault(value):
    return isinstance(value, dict) and "code" in value


# --- The law runner ---------------------------------------------------------

def _always_holds(params):
    """A law that holds for every subject: no messages, ever."""
    return []


def _requires_positive(params):
    """Holds when params['n'] is positive; one message otherwise."""
    if params["n"] > 0:
        return []
    return [f"n must be positive, got {params['n']}"]


def _requires_even(params):
    """Holds when params['n'] is even; one message otherwise."""
    if params["n"] % 2 == 0:
        return []
    return [f"n must be even, got {params['n']}"]


def _probe_law():
    """law assembles a Law of its three fields — identifier, statement, check —
    storing the check predicate unchanged so it still returns the empty list when
    the property holds and a non-empty list when it does not."""
    bad = []
    built = law("positive", "n is positive", _requires_positive)
    if built.get("identifier") != "positive":
        bad.append(f"law(...).identifier -> {built.get('identifier')!r}, expected 'positive'")
    if built.get("statement") != "n is positive":
        bad.append(f"law(...).statement -> {built.get('statement')!r}, expected 'n is positive'")
    stored = built.get("check")
    if not callable(stored):
        bad.append(f"law(...).check is not callable: {stored!r}")
        return bad
    if stored({"n": 5}) != []:
        bad.append("the stored check should return [] when the property holds")
    if not (isinstance(stored({"n": -1}), list) and stored({"n": -1})):
        bad.append("the stored check should return a non-empty list when it is violated")
    return bad


def _violation_set(violations):
    """A list of Violation dicts as a set of hashable tuples; order not asserted."""
    return {
        (v["identifier"], v["statement"], v["subject"], tuple(v["messages"]))
        for v in violations
    }


def _probe_verify_laws():
    """verify_laws applies each law's check to each subject, tallies passed and
    total, and collects one Violation per failed pair carrying the law identifier,
    statement, subject name and the check's messages. passed + len(violations) ==
    total holds for every run."""
    bad = []
    holds = law("holds", "every subject holds", _always_holds)
    positive = law("positive", "n is positive", _requires_positive)
    even = law("even", "n is even", _requires_even)

    cases = [
        {
            "laws": [holds, holds],
            "subjects": [{"name": "s_a", "params": {"n": 1}}, {"name": "s_b", "params": {"n": 2}}],
            "passed": 4,
            "total": 4,
            "violations": [],
        },
        {
            "laws": [holds, positive],
            "subjects": [{"name": "s_good", "params": {"n": 5}}, {"name": "s_bad", "params": {"n": -1}}],
            "passed": 3,
            "total": 4,
            "violations": [{"identifier": "positive", "statement": "n is positive", "subject": "s_bad", "messages": ["n must be positive, got -1"]}],
        },
        {
            "laws": [positive, even],
            "subjects": [{"name": "s_odd", "params": {"n": 3}}, {"name": "s_neg", "params": {"n": -2}}],
            "passed": 2,
            "total": 4,
            "violations": [
                {"identifier": "positive", "statement": "n is positive", "subject": "s_neg", "messages": ["n must be positive, got -2"]},
                {"identifier": "even", "statement": "n is even", "subject": "s_odd", "messages": ["n must be even, got 3"]},
            ],
        },
    ]

    for case in cases:
        got = verify_laws(case["laws"], case["subjects"])
        if not isinstance(got, dict):
            bad.append(f"verify_laws returned {got!r}, expected a LawRun dict")
            continue
        if got.get("passed") != case["passed"]:
            bad.append(f"verify_laws passed={got.get('passed')}, expected {case['passed']}")
        if got.get("total") != case["total"]:
            bad.append(f"verify_laws total={got.get('total')}, expected {case['total']}")
        if _violation_set(got.get("violations", [])) != _violation_set(case["violations"]):
            bad.append(f"verify_laws violations={got.get('violations')}, expected {case['violations']}")
        if got.get("passed", 0) + len(got.get("violations", [])) != got.get("total"):
            bad.append(f"verify_laws: passed + len(violations) != total: {got}")
    return bad


# --- The environment-variable reader ----------------------------------------

_DECLS = [
    {"name": "DB", "type_name": "str", "required": True},
    {"name": "SIZE", "type_name": "int", "required": True},
    {"name": "FLAG", "type_name": "bool", "required": False},
]


def _probe_resolve_env():
    """resolve_env resolves the raw map against the declarations: a present valid
    variable coerces, an absent optional becomes NOTHING, an absent required or an
    uncoercible value is a failure, and every failure is collected into one fault
    that names each failing variable."""
    bad = []

    ok = resolve_env(_DECLS, {"DB": "postgres://x", "SIZE": "10", "FLAG": "yes"})
    if _is_fault(ok):
        bad.append(f"an all-valid raw map should resolve, got fault {ok}")
    else:
        values = ok.get("values", {})
        if values.get("DB") != "postgres://x" or values.get("SIZE") != 10 or values.get("FLAG") is not True:
            bad.append(f"resolved values wrong: {values}")

    opt_absent = resolve_env(_DECLS, {"DB": "d", "SIZE": "1", "FLAG": NOTHING})
    if _is_fault(opt_absent) or opt_absent.get("values", {}).get("FLAG") != NOTHING:
        bad.append(f"an absent optional should resolve to NOTHING: {opt_absent}")

    req_absent = resolve_env(_DECLS, {"DB": NOTHING, "SIZE": "1", "FLAG": NOTHING})
    if not _is_fault(req_absent):
        bad.append(f"an absent required variable should fault: {req_absent}")
    elif "DB" not in req_absent.get("message", ""):
        bad.append(f"the fault should name the missing required variable: {req_absent}")

    uncoercible = resolve_env(_DECLS, {"DB": "d", "SIZE": "not-an-int", "FLAG": NOTHING})
    if not _is_fault(uncoercible):
        bad.append(f"an uncoercible value should fault: {uncoercible}")
    elif "SIZE" not in uncoercible.get("message", ""):
        bad.append(f"the fault should name the uncoercible variable: {uncoercible}")

    both = resolve_env(_DECLS, {"DB": NOTHING, "SIZE": "bad", "FLAG": NOTHING})
    if not _is_fault(both):
        bad.append(f"several failures should still fault: {both}")
    elif not ("DB" in both.get("message", "") and "SIZE" in both.get("message", "")):
        bad.append(f"one fault should name every failing variable together: {both.get('message')!r}")
    return bad


def _probe_read_env():
    """read_env reads the environment once through its boundary, coerces each
    declared variable, fills an absent optional with NOTHING, and faults when a
    required variable is missing. A key variable passes through, and its secret
    value never appears in a fault."""
    bad = []
    decls = [
        {"name": "HU_DB", "type_name": "str", "required": True},
        {"name": "HU_OPT", "type_name": "int", "required": False},
        {"name": "HU_KEY", "type_name": "key", "required": True},
    ]
    names = ["HU_DB", "HU_OPT", "HU_KEY"]
    saved = {name: os.environ.get(name) for name in names}
    secret = "sk-TOPSECRET-nevershown"
    try:
        os.environ.pop("HU_OPT", None)
        os.environ["HU_DB"] = "mydb"
        os.environ["HU_KEY"] = secret

        got = read_env(decls)
        if _is_fault(got):
            bad.append(f"a valid environment should return EnvValues, got fault {got}")
        else:
            values = got.get("values", {})
            if values.get("HU_DB") != "mydb":
                bad.append(f"HU_DB should be read from the environment: {values}")
            if values.get("HU_OPT") != NOTHING:
                bad.append(f"an absent optional HU_OPT should be NOTHING: {values}")
            if values.get("HU_KEY") != secret:
                bad.append("a key variable should pass through as its string")

        os.environ.pop("HU_DB", None)
        missing = read_env(decls)
        if not _is_fault(missing):
            bad.append(f"a missing required HU_DB should fault: {missing}")
        else:
            if "HU_DB" not in missing.get("message", ""):
                bad.append(f"the fault should name the missing variable: {missing}")
            if secret in str(missing):
                bad.append("a key variable's secret value must never appear in the fault")
    finally:
        for name, value in saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
    return bad


def run():
    probes = {
        "law": _probe_law(),
        "verify_laws": _probe_verify_laws(),
        "resolve_env": _probe_resolve_env(),
        "read_env": _probe_read_env(),
    }
    violations = [(name, messages) for name, messages in probes.items() if messages]
    for name, messages in violations:
        print(f"FAIL HU-probe [{name}]: {messages}")
    passed = sum(1 for messages in probes.values() if not messages)
    print(f"HU laws: {passed} passed, {len(violations)} failed, {len(probes)} total")
    return 0 if not violations else 1


if __name__ == "__main__":
    raise SystemExit(run())
