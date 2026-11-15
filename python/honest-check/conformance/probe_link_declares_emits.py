"""Conformance probe for honest-check's link_declares_emits.

Scenario (specs/features/honest-check.feature, Scenario: link_declares_emits):
    Given ctx: CheckContext and fdef: Node
    When link_declares_emits is called
    Then it returns true when a function carries a @link decorator that passes an `emits`
    keyword - the emits vocabulary HC-P017 requires of an HTTP-producing link - read from
    the decorator call the way is_boundary_decorator reads `boundary`.

The probe parses each decorated function with the real honest-parse grammar, builds a
CheckContext, hands the function_definition node to the real function, and checks the
boolean against the literal the scenario fixes.
"""

import honest_parse

# Each case: a decorated function and whether it carries @link(emits=...).
_CASES = [
    {"src": "@link(emits=events)\ndef h():\n    pass\n", "expect": True},     # @link passes emits
    {"src": "@link(boundary=True)\ndef h():\n    pass\n", "expect": False},   # @link, no emits keyword
    {"src": "@link\ndef h():\n    pass\n", "expect": False},                  # bare @link, no emits
    {"src": "def h():\n    pass\n", "expect": False},                         # no @link at all
    {"src": "@other(emits=events)\ndef h():\n    pass\n", "expect": False},   # emits on a non-@link decorator
]


def _ctx(src):
    source = src.encode("utf-8")
    tree = honest_parse.parse(source, "python")
    root = tree.root_node
    return {
        "root": root,
        "nodes": honest_parse.walk(root),
        "aliases": {},
        "roles": {},
        "source": source,
        "path": "link.py",
        "rule_config": {"HC-OR003": {"min_run": 3}},
    }


def _fdef_node(ctx):
    for node in ctx["nodes"]:
        if node.type == "function_definition":
            return node
    return None


def probe_link_declares_emits():
    """A function carrying @link(emits=...) declares emits; @link without emits, a bare @link, no @link, or emits on another decorator does not (HC-P017)."""
    try:
        from honest_check import link_declares_emits
    except ImportError as exc:
        return [f"cannot import link_declares_emits: {exc}"]

    bad = []
    for case in _CASES:
        ctx = _ctx(case["src"])
        fdef = _fdef_node(ctx)
        if fdef is None:
            bad.append(f"probe setup: no function_definition parsed from {case['src']!r}")
            continue
        try:
            got = link_declares_emits(ctx, fdef)
        except Exception as exc:
            bad.append(f"link_declares_emits({case['src']!r}) raised {exc!r}")
            continue
        if got != case["expect"]:
            bad.append(f"link_declares_emits({case['src']!r}) -> {got!r}, expected {case['expect']!r}")
    return bad
