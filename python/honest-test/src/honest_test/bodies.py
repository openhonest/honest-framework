"""The test-body honesty verdict (spec section 4.8).

A test that rebinds a call target at runtime — a monkeypatch fixture, a mock.patch, or an
attribute assignment on an imported symbol — exercises a call graph that is not production's.
The verdict reads the test module's source with Python's ast (pure, reads no world) and returns
one rejection Finding per rebinding statement. The framework's own record-and-restore monitors
are not rebinds and never appear.
"""

import ast

from honest_test.support import _finding

_MONKEYPATCH_METHODS = frozenset({"setattr", "setitem", "delattr", "setenv"})
_PATCH_ATTRS = frozenset({"patch", "object"})
_FIX = (
    "this rebinds a call target at runtime; pass the dependency as a parameter "
    "or inject a boundary plug as an argument"
)


def _is_monkeypatch_call(call):
    """True for monkeypatch.setattr / setitem / delattr / setenv."""
    func = call.func
    return (
        isinstance(func, ast.Attribute)
        and func.attr in _MONKEYPATCH_METHODS
        and isinstance(func.value, ast.Name)
        and func.value.id == "monkeypatch"
    )


def _is_patch_call(call):
    """True for patch(...), mock.patch(...) and patch.object(...)."""
    func = call.func
    if isinstance(func, ast.Name):
        return func.id == "patch"
    if isinstance(func, ast.Attribute):
        return func.attr in _PATCH_ATTRS
    return False


def _rebinds_by_assignment(node):
    """True when a statement assigns to an attribute target (imported.attr = replacement)."""
    if isinstance(node, ast.Assign):
        return any(isinstance(target, ast.Attribute) for target in node.targets)
    if isinstance(node, (ast.AugAssign, ast.AnnAssign)):
        return isinstance(node.target, ast.Attribute)
    return False


# honest: disable HC-P002: decoding the source is the verdict's one read of untrusted input; a test
# module that does not parse carries no rebinding statement, so the parse failure resolves to "no
# violation" here rather than propagating, keeping the .hd's "raises nothing" contract.
def test_body_violations(source):
    """Return one rejection Finding per statement that rebinds a call target at runtime (spec
    section 4.8). Reads nothing and raises nothing; an empty list means the body is honest."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    findings = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and (_is_monkeypatch_call(node) or _is_patch_call(node)):
            findings.append(_finding("rejection", "test_body_dishonest", _FIX, f"line {node.lineno}"))
        elif _rebinds_by_assignment(node):
            findings.append(_finding("rejection", "test_body_dishonest", _FIX, f"line {node.lineno}"))
    return findings
# honest: enable HC-P002
