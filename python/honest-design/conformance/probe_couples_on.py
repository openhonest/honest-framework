# scenario: couples_on says whether a world-side target couples two modules
# inherits: hd=python/honest-design/honest-design-side-policy.hd::couples_on -> feature=python/honest-design/features/honest-design.feature::couples_on says whether a world-side target couples two modules

_CASES = [("clock", False), ("file:design/data", True), ("database:given", False)]


def probe_couples_on():
    from honest_design.side_policy import couples_on

    failures = []
    for target, expected in _CASES:
        actual = couples_on(target)
        if actual is not expected:
            failures.append(f"Expected {target} to yield {expected!r}, received {actual!r}")
    return failures
