"""extract_chains recognizes every chain the source declares (honest-check.hd, spec
section 3.4, section 3.5). It is the public counterpart of the chain honest-check builds
in its declaration graph for HC-R002 and HC002: honest-test hands in the parsed root, the
source bytes, and the alias map resolve_aliases returned, and extract_chains returns one
ChainDecl { name, links } per chain the file declares — the chain's assigned name and the
ordered names of its link functions.

A chain is a module-level assignment whose right side is a `chain(...)` call (recognized
through the alias map, so `chain(...)` and an aliased `c(...)` both count); name is the
assignment target, links are the positional argument names in source order. Pins the
contract: name and ordered links for a direct chain, the same through an alias, and the
empty list when the file declares no chain. A stub returning [] fails cases 1 and 2.
"""

_CASES = [
    # A direct chain(...) assignment: name is the target, links are the positional args in order.
    {
        "source": "from honest_type import chain\nreport = chain(classify, shape, emit)\n",
        "want": [{"name": "report", "links": ["classify", "shape", "emit"]}],
    },
    # The same through an alias: `chain as c`, then `c(...)` still resolves to a chain.
    {
        "source": "from honest_type import chain as c\nflow = c(read, write)\n",
        "want": [{"name": "flow", "links": ["read", "write"]}],
    },
    # Two chains in one file come back in source order.
    {
        "source": "from honest_type import chain\na = chain(one)\nb = chain(two, three)\n",
        "want": [{"name": "a", "links": ["one"]}, {"name": "b", "links": ["two", "three"]}],
    },
    # A file with no chain assignment yields the empty list; a vocabulary is not a chain.
    {
        "source": "from honest_type import vocabulary\nv = vocabulary(is_x)\n",
        "want": [],
    },
    # A call to a function that is not a framework constructor is not a chain, even when it is
    # assigned to a name: `other` is not in the constructor set and resolves through no alias.
    {
        "source": "from honest_type import chain\nx = other(a, b)\n",
        "want": [],
    },
    # A dotted call is not a chain: the called function is an attribute (`mod.chain`), not a
    # bare identifier, so it resolves to no constructor.
    {
        "source": "from honest_type import chain\nx = mod.chain(a, b)\n",
        "want": [],
    },
    # A chain call assigned to a non-identifier target (an attribute) is not a chain
    # declaration: a chain is a module-level name binding, so the target must be a bare name.
    {
        "source": "from honest_type import chain\nobj.attr = chain(a, b)\n",
        "want": [],
    },
    # A bare `chain(...)` with no import is still recognized: `chain` is a known constructor
    # name, so it resolves without an alias. This exercises the constructor-name branch, which
    # an aliased import would otherwise decide.
    {
        "source": "c = chain(classify, emit)\n",
        "want": [{"name": "c", "links": ["classify", "emit"]}],
    },
]


def probe_extract_chains():
    try:
        from honest_check.declgraph import extract_chains, resolve_aliases
    except ImportError as exc:
        return [f"cannot import extract_chains from honest_check.declgraph: {exc}"]
    from honest_parse import parse

    bad = []
    for case in _CASES:
        source = case["source"].encode("utf-8")
        root = parse(source, "python").root_node
        aliases = resolve_aliases(root, source)
        got = extract_chains(root, source, aliases)
        if got != case["want"]:
            bad.append(
                f"extract_chains over {case['source']!r} -> {got!r}, expected {case['want']!r}"
            )
    return bad
