"""Honest probe for honest-check's link_locals (feature Scenario: link_locals).

Scenario: link_locals returns the names local to a link — its parameters plus the
names it assigns in its own body — so a read of one of these is not a read of a
module global (HC008).

Signature: link_locals(fdef: Node, body: list<Node>). The probe parses one link,
hands its real function_definition node as `fdef` and its body's statement nodes as
`body`, and pins the exact set of local names: the two parameters plus the two
assigned names. honest-parse is built; every node is a real tree-sitter node.

Container caveat: the scenario fixes WHICH names are local, not whether the
function returns them as a set, a list, or something else. The probe reads the
return through `set(...)`, so it holds for any names collection. See GAPS.
"""

from honest_parse import parse, walk


# The link under test: parameters a, b; assigns x and y; reads x in a return.
_SRC = "def f(a, b):\n    x = 1\n    y = 2\n    return x\n"
_EXPECT = {"a", "b", "x", "y"}


def _fdef_and_body():
    root = parse(_SRC.encode(), "python").root_node
    fdef = [n for n in walk(root) if n.type == "function_definition"][0]
    block = fdef.child_by_field_name("body")
    return fdef, list(block.named_children)


def probe_link_locals():
    """link_locals returns a link's parameter names plus the names it assigns."""
    try:
        from honest_check import link_locals
    except ImportError as exc:
        return [f"cannot import link_locals: {exc}"]

    bad = []
    fdef, body = _fdef_and_body()
    got = link_locals(fdef, body)
    if set(got) != _EXPECT:
        bad.append(
            f"link_locals(<def f(a, b)>) -> {sorted(set(got))}, expected {sorted(_EXPECT)}"
        )
    return bad
