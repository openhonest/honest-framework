# scenario: resolve_pure_calls
# inherits: hd=python/honest-check/honest-check.hd::resolve_pure_calls -> feature=specs/features/honest-check.feature::resolve_pure_calls returns invalid_role for an interior unpublished target -> test=python/honest-check/conformance/probe_resolve_pure_calls_interior.py::probe_resolve_pure_calls_interior
"""Check that the resolver returns invalid_role for an interior unpublished target.

The scenario: a caller declares a pure_call onto a plain, side-effect-free `fn`
that lives in a module in view, but that module publishes it through no entry and
no export surface. The function exists and is the plain fn role, yet it is
interior and unpublished, so pure_target_is_callable says false and the
occurrence provides no dependency evidence: the resolution's status is
invalid_role, not resolved.

The target module's `.hd` is real text parsed by honest-design's read_hd into the
Declaration shape honest-check reads and never constructs, so the "interior and
unpublished" fact is genuine data: utils is NOT boundaryless — it declares a
`boundary_in` and an `entry` that reaches `answer` — so it has a real surface, yet
`helper` is reached by no entry and named by no export. A boundaryless module (one
with no boundary and no surface) would publish all its functions; utils is the
other case, a module with a surface in which `helper` is genuinely interior. This
mirrors probe_pure_target_is_callable_interior.py, which distinguishes published
from interior by parsing real `.hd` text.
"""

# caller declares one pure_call onto utils.helper.
_CALLER_SRC = (
    "module caller\n\n"
    "  fn load : () -> str\n"
    '    pure_call "utils.helper"\n'
)

# utils has a REAL surface, so it is not boundaryless: it declares a `boundary_in`
# and an `entry` that reaches `answer`. `helper` is a plain, side-effect-free fn
# reached by no entry and named by no export, so it is genuinely interior and
# unpublished in a module that has a surface.
_UTILS_INTERIOR_SRC = (
    "module utils\n\n"
    '  boundary_in fn enter : (x: str) -> str note "the input boundary, a real surface"\n'
    '  fn answer : (x: str) -> str note "the published pure way in, reached by an entry"\n'
    '  fn helper : (x: str) -> str note "an interior function no entry reaches"\n'
    '  entry "import utils" -> answer\n'
)

# The occurrence resolves, module and caller parsed, but the target is interior
# and unpublished, so the status is invalid_role, not resolved.
_EXPECTED = [
    {
        "caller": "load",
        "target": "utils.helper",
        "module": "utils",
        "status": "invalid_role",
    }
]


def probe_resolve_pure_calls_interior():
    """resolve_pure_calls returns invalid_role for a pure call onto an interior, unpublished plain fn."""
    try:
        from honest_check.seams import resolve_pure_calls
    except ImportError as exc:
        return [f"cannot import resolve_pure_calls: {exc}"]
    try:
        from honest_design import read_hd
    except ImportError as exc:
        return [f"cannot import honest_design.read_hd: {exc}"]

    module = read_hd(_CALLER_SRC)["ok"]["modules"][0]
    utils = read_hd(_UTILS_INTERIOR_SRC)["ok"]["modules"][0]
    declarations = {utils["name"]: utils}

    got = resolve_pure_calls(module, declarations)
    if got != _EXPECTED:
        return [f"resolve_pure_calls returned {got!r}, expected {_EXPECTED!r}"]
    return []
