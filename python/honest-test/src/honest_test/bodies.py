"""The test-body honesty verdict (spec section 4.8).

A test that rebinds a call target at runtime — a monkeypatch fixture, a mock.patch, or an
attribute assignment on an imported symbol — exercises a call graph that is not production's.
The verdict reads the test module's source with Python's ast (pure, reads no world) and returns
one rejection Finding per rebinding statement. The framework's own record-and-restore monitors
are not rebinds and never appear.
"""

import ast

from honest_test._util import _pick, _read_or
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


_PATCH_PREDICATES = {
    ast.Name: lambda func: func.id == "patch",
    ast.Attribute: lambda func: func.attr in _PATCH_ATTRS,
}


def _is_patch_call(call):
    """True for patch(...), mock.patch(...) and patch.object(...)."""
    func = call.func
    predicate = _read_or(_PATCH_PREDICATES, type(func), lambda func: False)
    return predicate(func)


_REBIND_PREDICATES = {
    ast.Assign: lambda node: any(isinstance(target, ast.Attribute) for target in node.targets),
    ast.AugAssign: lambda node: isinstance(node.target, ast.Attribute),
    ast.AnnAssign: lambda node: isinstance(node.target, ast.Attribute),
}


def _rebinds_by_assignment(node):
    """True when a statement assigns to an attribute target (imported.attr = replacement)."""
    predicate = _read_or(_REBIND_PREDICATES, type(node), lambda node: False)
    return predicate(node)


def test_body_violations(source):
    """Return one rejection Finding per statement that rebinds a call target at runtime (spec
    section 4.8). Reads nothing and raises nothing; an empty list means the body is honest."""
    try:  # honest: ignore HC-P002: decoding untrusted source is this verdict's one boundary read; a test module that does not parse carries no rebinding statement, so the parse failure resolves to "no violation"
        tree = ast.parse(source)
    except SyntaxError:
        return []
    findings = []
    for node in ast.walk(tree):
        rebinds = (
            (isinstance(node, ast.Call)
             and (_is_monkeypatch_call(node) or _is_patch_call(node)))
            or _rebinds_by_assignment(node)
        )
        _pick(
            rebinds,
            lambda: findings.append(
                _finding("rejection", "test_body_dishonest", _FIX, f"line {node.lineno}")),
            lambda: None,
        )
    return findings
