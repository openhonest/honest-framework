"""Conformance fragment for the verify_laws scenario (honest-test.feature ~426).

Scenario: verify_laws runs every law against every subject and returns the run
  record.
  Then it applies each law's check to each subject's params and returns a LawRun
  of passed, total and violations.
  And it counts the law-and-subject pairs that held as passed and the pairs
  checked as total.
  And it collects one Violation per failed pair, each naming the law's
  identifier, its statement, the subject, and the messages the check returned.

Cases are data; one pure probe feeds them to the real function and returns a list
of failure strings (empty when every case holds). No classes, no mocks: it calls
the real honest_test.law to build each Law from a small pure check predicate
defined here (a real function as test input) and the real honest_test.verify_laws
to produce the LawRun.

This is its own fragment file so the other scenarios' fragments never collide
with it.
"""

from honest_test import law, verify_laws


# --- pure check predicates, the real functions handed to each law as test input.
# Each takes one subject's params and returns the violation messages, empty when
# the property holds for that subject.

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


# Laws built by the real law(), so a stub law() is red here too.
_L_HOLDS = law("holds", "every subject holds", _always_holds)
_L_POSITIVE = law("positive", "n is positive", _requires_positive)
_L_EVEN = law("even", "n is even", _requires_even)


_CASES = [
    # All subjects satisfy all laws: passed == total, no violations. This is the
    # explicit absence case — violations written out as the empty list.
    {
        "laws": [_L_HOLDS, _L_HOLDS],
        "subjects": [
            {"name": "s_a", "params": {"n": 1}},
            {"name": "s_b", "params": {"n": 2}},
        ],
        "expect_passed": 4,
        "expect_total": 4,
        "expect_violations": [],
    },
    # One subject violates one law: 2 laws x 2 subjects = 4 pairs, one fails, so
    # passed == 3 and exactly one Violation naming that law, statement, subject
    # and the message the check returned.
    {
        "laws": [_L_HOLDS, _L_POSITIVE],
        "subjects": [
            {"name": "s_good", "params": {"n": 5}},
            {"name": "s_bad", "params": {"n": -1}},
        ],
        "expect_passed": 3,
        "expect_total": 4,
        "expect_violations": [
            {
                "law": "positive",
                "statement": "n is positive",
                "subject": "s_bad",
                "messages": ["n must be positive, got -1"],
            },
        ],
    },
    # Two laws x two subjects with two known failures: positive fails on n=-2,
    # even fails on n=3. passed == 2, total == 4, two Violations with exact
    # content.
    {
        "laws": [_L_POSITIVE, _L_EVEN],
        "subjects": [
            {"name": "s_odd", "params": {"n": 3}},
            {"name": "s_neg", "params": {"n": -2}},
        ],
        "expect_passed": 2,
        "expect_total": 4,
        "expect_violations": [
            {
                "law": "positive",
                "statement": "n is positive",
                "subject": "s_neg",
                "messages": ["n must be positive, got -2"],
            },
            {
                "law": "even",
                "statement": "n is even",
                "subject": "s_odd",
                "messages": ["n must be even, got 3"],
            },
        ],
    },
]


def _violation_set(violations):
    """A list of Violation dicts as a set of hashable tuples; order not asserted."""
    return {
        (v["law"], v["statement"], v["subject"], tuple(v["messages"]))
        for v in violations
    }


def probe_verify_laws():
    """verify_laws applies each law's check to each subject, tallies passed and total, and collects one Violation per failed pair carrying the law identifier, statement, subject name and the check's messages."""
    bad = []
    for case in _CASES:
        got = verify_laws(case["laws"], case["subjects"])
        if not isinstance(got, dict):
            bad.append(f"verify_laws returned {got!r}, expected a LawRun dict")
            continue
        if got.get("passed") != case["expect_passed"]:
            bad.append(
                f"verify_laws(...) passed={got.get('passed')}, "
                f"expected {case['expect_passed']}"
            )
        if got.get("total") != case["expect_total"]:
            bad.append(
                f"verify_laws(...) total={got.get('total')}, "
                f"expected {case['expect_total']}"
            )
        got_v = _violation_set(got.get("violations", []))
        want_v = _violation_set(case["expect_violations"])
        if got_v != want_v:
            bad.append(
                f"verify_laws(...) violations={got_v}, expected {want_v}"
            )
        # The arithmetic the spec pins: passed + len(violations) == total.
        if got.get("passed", 0) + len(got.get("violations", [])) != got.get("total"):
            bad.append(
                f"verify_laws(...) passed + len(violations) != total: "
                f"{got.get('passed')} + {len(got.get('violations', []))} "
                f"!= {got.get('total')}"
            )
    return bad


def run():
    bad = probe_verify_laws()
    for line in bad:
        print(line)
    print(f"probe_verify_laws: {len(bad)} failure(s)")
    return bad


if __name__ == "__main__":
    import sys

    sys.exit(1 if run() else 0)
