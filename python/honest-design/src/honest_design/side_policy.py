"""Shared pure policy for coupling on declared world sides."""

# inherits: hd=python/honest-design/honest-design-side-policy.hd::couples_on -> feature=python/honest-design/features/honest-design.feature::couples_on says whether a world-side target couples two modules -> test=python/honest-design/conformance/probe_couples_on.py::probe_couples_on
# hd: couples_on
def couples_on(target: str) -> bool:
    """Classify a declared world-side target for static coupling."""
    _, colon, name = target.partition(":")
    return bool(colon) and name != "given"
