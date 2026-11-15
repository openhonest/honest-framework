"""Honest probe for honest-check's longest_shared_run (Scenario: longest_shared_run).

longest_shared_run returns the length of the longest run of consecutive equivalent
call names two call sequences share — a contiguous common substring over the two
lists — and 0 when they share no adjacent run (HC-OR003). The cases are plain
string lists, each paired with the run length the scenario fixes, including the
explicit 0 case for sequences that share no adjacent run.
"""

# Each case: two call-name sequences, and the length of their longest shared run.
_CASES = [
    {"a": ["a", "b", "c", "d"], "b": ["x", "b", "c", "y"], "expect": 2},   # shared run b,c
    {"a": ["a", "b", "c", "d"], "b": ["z", "a", "b", "c", "d"], "expect": 4},  # whole a,b,c,d
    {"a": ["a", "b"], "b": ["b", "a"], "expect": 1},                       # common elements, not adjacent -> run 1
    {"a": ["a", "b", "c"], "b": ["x", "y", "z"], "expect": 0},             # no shared adjacent run
]


def probe_longest_shared_run():
    """longest_shared_run returns the length of the longest contiguous common run."""
    try:
        from honest_check import longest_shared_run
    except ImportError as exc:
        return [f"cannot import longest_shared_run: {exc}"]

    ctx = {
        "root": None,
        "nodes": [],
        "aliases": {},
        "roles": {},
        "source": b"",
        "path": "case.py",
        "rule_config": {},
    }

    bad = []
    for case in _CASES:
        got = longest_shared_run(ctx, case["a"], case["b"])
        if got != case["expect"]:
            bad.append(
                f"longest_shared_run({case['a']!r}, {case['b']!r}) -> {got!r}, "
                f"expected {case['expect']!r}"
            )
    return bad
