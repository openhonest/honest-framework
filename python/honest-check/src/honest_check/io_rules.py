"""Locate watched I/O operations inside the host functions checked by HC-P004."""

from honest_parse import language_of

from ._util import choose, read_or
from .analysis import watched
from .decorators import _DOOR_ROLES, in_non_boundary_function
from .diagnostics import diagnostic
from .nodes import _field, _SCOPE_BOUNDARIES, _text

_IO_WATCH = {
    "python": {"open", "input", "os.*", "socket.*", "requests.*", "urllib.*", "subprocess.*", "shutil.*"},
    "javascript": {"fetch", "XMLHttpRequest", "localStorage.*", "sessionStorage.*"},
    "ruby": {"File.*", "IO.*"},
    "go": {"os.*", "ioutil.*"},
}

_NAMED_OWNERS = {
    "javascript": {"function_declaration"},
    "ruby": {"method", "singleton_method"},
    "go": {"function_declaration", "method_declaration"},
}
_OWNERS = _SCOPE_BOUNDARIES | {"method", "singleton_method", "method_declaration", "func_literal"}
_OPERATIONS = {"call", "call_expression", "new_expression"}


# inherits: hd=python/honest-check/honest-check.hd::_call_target_watched -> feature=specs/features/honest-check.feature::_call_target_watched matches only supported static operation heads -> test=python/honest-check/conformance/probe_p004_call_target_watched_static.py::probe_p004_call_target_watched_static
# hd: _call_target_watched
def _call_target_watched(ctx, call, watch):
    """Match the statically named operation head for the selected host grammar."""
    match call.type:
        case "new_expression":
            constructor = _field(call, "constructor")
            return (
                constructor is not None and constructor.type == "identifier"
                and constructor.text == b"XMLHttpRequest" and watched(constructor, watch)
            )
    target = choose(_field(call, "method") is not None, call, _field(call, "function"))
    return target is not None and watched(target, watch)


# inherits: hd=python/honest-check/honest-check.hd::_hc_p004 -> feature=specs/features/honest-check.feature::_hc_p004 reports watched operations in named non-boundary host functions -> test=python/honest-check/conformance/probe_p004_hc_p004_host_functions.py::probe_p004_hc_p004_host_functions
# inherits: hd=python/honest-check/honest-check.hd::_hc_p004 -> feature=specs/features/honest-check.feature::_hc_p004 uses the nearest owner and its own boundary evidence -> test=python/honest-check/conformance/probe_p004_hc_p004_nearest_owner.py::probe_p004_hc_p004_nearest_owner
# hd: _hc_p004
def _hc_p004(ctx):
    """Report each watched operation inside its nearest non-boundary named function."""
    language = read_or(language_of(ctx["path"]), "ok", "python")
    watch = read_or(_IO_WATCH, language, set())
    operations = filter(
        lambda node: node.type in _OPERATIONS and _call_target_watched(ctx, node, watch),
        ctx["nodes"],
    )
    match language:
        case "python":
            return [
                diagnostic(ctx, "HC-P004", "error", "I/O inside a non-boundary function", call)
                for call in filter(lambda call: in_non_boundary_function(ctx, call), operations)
            ]

    named = read_or(_NAMED_OWNERS, language, set())
    boundary_rows = {
        comment.start_point.row for comment in filter(
            lambda node: language == "javascript" and node.type == "comment"
            and node.text.strip() == b"// honest: boundary",
            ctx["nodes"],
        )
    }
    findings = []
    for call in operations:
        owner = call.parent
        while owner is not None and owner.type not in _OWNERS:
            owner = owner.parent
        name = _text(_field(owner, "name"))
        eligible = (
            owner is not None and owner.type in named and name is not None
            and read_or(ctx["roles"], name, "") not in _DOOR_ROLES
            and owner.start_point.row not in boundary_rows
            and owner.start_point.row - 1 not in boundary_rows
        )
        match eligible:
            case True:
                findings.append(diagnostic(ctx, "HC-P004", "error", "I/O inside a non-boundary function", call))
    return findings
