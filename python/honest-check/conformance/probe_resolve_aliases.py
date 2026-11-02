"""resolve_aliases recovers the import aliases a framework call resolves through
(honest-check.hd, spec section 3.3, section 3.5). It is the public counterpart of the
alias map check_source builds internally: honest-test parses a file once and hands the
root node and the source bytes in, and resolve_aliases returns the map from each local
name bound by a `honest_type` import to its canonical constructor name, so an aliased
call (`from honest_type import chain as c`) still resolves to the real constructor.

Pins the contract, not the internals: a plain import maps a name to itself, an aliased
import maps the local alias to the canonical name, and a file that imports nothing from
honest_type yields the empty map. A stub returning {} fails case 1, so the probe is not
vacuous.
"""

_CASES = [
    # A plain import maps each imported name to itself; an aliased import maps the local
    # alias to the canonical constructor name.
    {
        "source": "from honest_type import chain, vocabulary as v\n",
        "want": {"chain": "chain", "v": "vocabulary"},
    },
    # An import from any other module contributes no alias.
    {
        "source": "from other import chain\nimport honest_type\n",
        "want": {},
    },
    # No honest_type import at all: the empty map.
    {
        "source": "x = 1\n",
        "want": {},
    },
]


def probe_resolve_aliases():
    try:
        from honest_check.declgraph import resolve_aliases
    except ImportError as exc:
        return [f"cannot import resolve_aliases from honest_check.declgraph: {exc}"]
    from honest_parse import parse

    bad = []
    for case in _CASES:
        source = case["source"].encode("utf-8")
        root = parse(source, "python").root_node
        got = resolve_aliases(root, source)
        if got != case["want"]:
            bad.append(
                f"resolve_aliases over {case['source']!r} -> {got!r}, expected {case['want']!r}"
            )
    return bad
