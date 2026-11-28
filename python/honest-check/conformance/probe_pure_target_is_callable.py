# scenario: pure_target_is_callable
# inherits: hd=python/honest-check/honest-check.hd::pure_target_is_callable -> feature=specs/features/honest-check.feature::pure_target_is_callable it splits target once on the first dot into the target module name and the target function name, reads the target module's Declaration off declarations without constructing one, touches no world and opens no file, and returns the single boolean, true only when the target module name is a key in declarations and that module declares a function of the target name whose role is the plain fn, declares no side effect at all, and is published by the target module as a pure way in through a valid entry or export -> test=python/honest-check/conformance/probe_pure_target_is_callable.py::probe_pure_target_is_callable
"""Honest probe for honest-check's pure_target_is_callable (base contract scenario).

The base scenario fixes the callability predicate for a cross-module pure
dependency (HC-REF012): the function splits target once on the first dot into a
module half and a function half, reads the named module's Declaration off the
declarations map, and returns a single boolean that is true only when every one
of these holds: the module half is a key in declarations, that module declares a
function of the function half, that function's role is the plain `fn`, it
declares no side effect at all, and the module publishes it as a pure way in
through a valid entry or export.

Two cases pin the behaviour against a stub:
  - a published pure fn ("utils.answer") whose module declares `answer` as a
    plain `fn` with no side effects and names it in an `entry` -> True. This is
    the non-trivial literal: a `return False` (or `return None`) stub fails it.
  - the malformed target "answer" with no dot (no module half) -> False, the
    explicit absence case named in the base Then. A `return True` stub fails it.

Every input Declaration is real: honest-design's read_hd parses the .hd text
into the Declaration shape honest-check reads and never constructs. The probe
builds no Declaration dict by hand and mocks nothing.
"""

# utils publishes answer: a plain fn, no side effects, named by an entry.
_SRC_UTILS_PUBLISHED = (
    "module utils\n\n"
    "  fn answer : (x: str) -> str\n\n"
    '  entry "call:answer" -> answer\n'
)

# Each case: the qualified target, the .hd text of each module in view keyed by
# the name read off its parse, and the exact boolean the predicate must return.
_CASES = [
    # Happy path: a function another module publishes as a pure way in -> True.
    {"target": "utils.answer", "sources": [_SRC_UTILS_PUBLISHED], "expect": True},
    # Absence: a string with no dot has no module half and is not callable -> False.
    {"target": "answer", "sources": [_SRC_UTILS_PUBLISHED], "expect": False},
]


def probe_pure_target_is_callable():
    """pure_target_is_callable returns the single bool: true only for a published pure fn, and false for a target with no module half."""
    try:
        from honest_check.seams import pure_target_is_callable
    except ImportError as exc:
        return [f"cannot import pure_target_is_callable: {exc}"]
    try:
        from honest_design import read_hd
    except ImportError as exc:
        return [f"cannot import honest_design.read_hd: {exc}"]

    bad = []
    for case in _CASES:
        declarations = {}
        for src in case["sources"]:
            module = read_hd(src)["ok"]["modules"][0]
            declarations[module["name"]] = module
        got = pure_target_is_callable(target=case["target"], declarations=declarations)
        if got is not case["expect"]:
            bad.append(
                f"pure_target_is_callable(target={case['target']!r}) -> "
                f"{got!r}, expected {case['expect']!r}"
            )
    return bad
