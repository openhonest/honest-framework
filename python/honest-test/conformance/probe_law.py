"""Conformance fragment for the law scenario (honest-test.feature).

Scenario: law states one property as data for the generative law runner.
  Then it returns a Law record of those three fields: the identifier, the
  plain-language statement, and the check.
  And check is the pure predicate the property is proven by — a function from
  one subject to a list of violation messages, empty when the property holds and
  one message per violation, which never raises and never returns a bare boolean.
  And it reads no world and returns pure data.

Cases are data; one pure probe feeds them to the real honest_test.law and returns
a list of failure strings (empty when every case holds). No classes, no mocks: the
check handed to law is a real pure predicate defined below and used as test input,
not a stand-in. The probe pins that law stores all three fields unchanged — in
particular that the check it returns is the same callable, still behaving — so a
stub returning an empty record cannot pass.

This is its own fragment file so the other scenarios' fragments never collide with
it. run_conformance.py / laws_htest.py are untouched.
"""

from honest_test import law


def _nonblank_name(params):
    """A pure predicate: the subject's name must be a non-blank string.

    Returns the empty list when it holds, one message per violation otherwise.
    This is the shape a Law's check carries — one subject's params to a list of
    violation messages, never a bare boolean, never a raise.
    """
    messages = []
    name = params.get("name")
    if not isinstance(name, str):
        messages.append(f"name {name!r} is not a string")
    elif name.strip() == "":
        messages.append("name is blank")
    return messages


def _positive_amount(params):
    """A pure predicate: the subject's amount must be greater than zero."""
    messages = []
    amount = params.get("amount")
    if amount is None:
        messages.append("amount is missing")
    elif amount <= 0:
        messages.append(f"amount {amount} is not positive")
    return messages


# Each row states the three fields handed to law and two probe subjects for its
# check: a holding case whose params produce the empty list, and a violating case
# whose params produce a non-empty list. The holding/violating pair is written out
# so a check stored as anything but the passed predicate is caught.
_CASES = [
    {
        "identifier": "name-nonblank",
        "statement": "every subject carries a non-blank name",
        "check": _nonblank_name,
        "holds_params": {"name": "widget"},
        "violates_params": {"name": "   "},
    },
    {
        "identifier": "amount-positive",
        "statement": "every subject's amount is greater than zero",
        "check": _positive_amount,
        "holds_params": {"amount": 5},
        "violates_params": {"amount": 0},
    },
]


def probe_law():
    """law assembles a Law of the three fields passed, storing the check predicate unchanged so it still returns an empty list when the property holds and a non-empty list when it does not."""
    bad = []
    for case in _CASES:
        got = law(case["identifier"], case["statement"], case["check"])

        if got["identifier"] != case["identifier"]:
            bad.append(
                f"law({case['identifier']!r}, ...).identifier -> "
                f"{got['identifier']!r}, expected {case['identifier']!r}"
            )
        if got["statement"] != case["statement"]:
            bad.append(
                f"law({case['identifier']!r}, ...).statement -> "
                f"{got['statement']!r}, expected {case['statement']!r}"
            )

        stored = got["check"]
        if not callable(stored):
            bad.append(
                f"law({case['identifier']!r}, ...).check is not callable: {stored!r}"
            )
            continue

        held = stored(case["holds_params"])
        if held != []:
            bad.append(
                f"law({case['identifier']!r}, ...).check({case['holds_params']}) "
                f"-> {held}, expected [] (the property holds)"
            )
        violated = stored(case["violates_params"])
        if not (isinstance(violated, list) and len(violated) >= 1):
            bad.append(
                f"law({case['identifier']!r}, ...).check({case['violates_params']}) "
                f"-> {violated}, expected a non-empty list of violation messages"
            )
    return bad


def run():
    bad = probe_law()
    for line in bad:
        print(line)
    print(f"probe_law: {len(bad)} failure(s)")
    return bad


if __name__ == "__main__":
    import sys

    sys.exit(1 if run() else 0)
