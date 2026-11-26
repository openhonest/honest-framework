# scenario: watched resolves static JavaScript member names independent of spacing
# inherits: hd=python/honest-check/honest-check.hd::watched -> feature=specs/features/honest-check.feature::watched resolves static JavaScript member names independent of spacing

from honest_check import build_context, watched


def probe_watched_javascript_members():
    cases = (
        (b"Math.random", "Math.random", True),
        (b"Math . random", "Math.random", True),
        (b'Math["random"]', 'Math["random"]', False),
        (b"makeMath().random", "makeMath().random", False),
    )
    failures = []
    for source, watch_name, expected in cases:
        root = build_context(source + b";", "case.js", {})["root"]
        target = root.named_children[0].named_children[0]
        actual = watched(target, {"Math.random", watch_name})
        if actual is not expected:
            failures.append(f"{source!r}: watched returned {actual!r}, expected {expected!r}")
    return failures
