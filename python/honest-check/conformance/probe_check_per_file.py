"""Honest probe for honest-check's check_per_file (feature Scenario: check_per_file).

check_per_file is the static per-file rule sub-core: it runs the HC-P purity rules, the
chain/link rules, the per-file state rules and the HC-HF feature-flag rules over the one
CheckContext build_context assembled, and returns the per-file findings as data. The feature
scenario names the HC-P purity rules; two have sharp, source-level triggers: any `if`
(outside the script guard) fires HC-P001, and a class declaration fires HC-P003. So the two
violation cases build real CheckContexts over source holding an `if` and over source holding
a class, demanding a Diagnostic with rule_id HC-P001 and HC-P003 in turn; the clean case
holds neither and demands the empty list. A `return []` stub passes the clean case and fails
both violation cases.

The input is a real parse: build_context parses the crafted source under honest-parse's Python
grammar and assembles the CheckContext check_per_file reads. No fabricated nodes.
"""

# Each case: crafted Python source (bytes), and the per-file-rule verdict it must produce.
_CASES = [
    {
        "desc": "a module-scope `if` fires HC-P001",
        "source": b"flag = True\nif flag:\n    y = 1\n",
        "must_contain": "HC-P001",
        "must_be_empty": False,
    },
    {
        "desc": "a class declaration fires HC-P003",
        "source": b"class Thing:\n    pass\n",
        "must_contain": "HC-P003",
        "must_be_empty": False,
    },
    {
        "desc": "a plain assignment is clean",
        "source": b"x = 1\n",
        "must_contain": None,
        "must_be_empty": True,
    },
]


def probe_check_per_file():
    """check_per_file fires HC-P001 on an `if` and HC-P003 on a class, and is silent on clean source."""
    try:
        from honest_check import build_context, check_per_file
    except ImportError as exc:
        return [f"cannot import check_per_file: {exc}"]

    bad = []
    for case in _CASES:
        ctx = build_context(source=case["source"], path="probe.py", rule_config={})
        got = check_per_file(ctx=ctx)
        ids = [d["rule_id"] for d in got]
        if case["must_be_empty"]:
            if got != []:
                bad.append(
                    f"check_per_file({case['desc']}) -> {ids}, expected no findings"
                )
        elif case["must_contain"] not in ids:
            bad.append(
                f"check_per_file({case['desc']}) -> {ids}, "
                f"expected a {case['must_contain']} finding"
            )
    return bad
