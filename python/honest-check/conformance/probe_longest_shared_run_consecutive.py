# scenario: longest_shared_run counts only consecutive matches across both sequences
# inherits: hd=python/honest-check/honest-check.hd::longest_shared_run -> feature=specs/features/honest-check.feature::longest_shared_run counts only consecutive matches across both sequences

from honest_check import build_context, longest_shared_run

_CASES = [
    ([], ["a"], 0),
    (["a"], [], 0),
    (["a", "b"], ["x", "y"], 0),
    (["a"], ["a"], 1),
    (["a", "b", "c"], ["x", "a", "b"], 2),
    (["x", "a", "b"], ["a", "b", "c"], 2),
    (["a", "b", "gap", "c"], ["a", "b", "c"], 2),
    (["r", "gap", "r", "r", "s"], ["r", "r", "other", "r", "r", "s"], 3),
]


def probe_longest_shared_run_consecutive():
    ctx = build_context(b"", "case.py", {})
    failures = []
    for calls_a, calls_b, expected in _CASES:
        actual = longest_shared_run(ctx, calls_a, calls_b)
        if actual != expected:
            failures.append(f"{calls_a!r} and {calls_b!r}: expected {expected}, got {actual}")
    return failures
