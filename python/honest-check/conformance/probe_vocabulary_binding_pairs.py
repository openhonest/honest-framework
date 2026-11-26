# scenario: vocabulary_binding_pairs
# inherits: hd=python/honest-check/honest-check.hd::vocabulary_binding_pairs -> feature=specs/features/honest-check.feature::vocabulary_binding_pairs
"""Honest probe for honest-check's vocabulary_binding_pairs (feature Scenario: vocabulary_binding_pairs).

Scenario: vocabulary_binding_pairs returns each (vocabulary calls, binding call) a
classify or link pairs by name: a classify(tokens, vocab, bind=b) pairs positional 2
with the `bind` keyword with the one vocab as its vocabulary list, and a
link(accepts=v, emits=e, bind=b) pairs by its keywords (HC004, HC005).

The cases construct vocabularies and a binding, then call classify or link.
Both resolved and unresolved references are exercised. The probe pins each pair,
read back by the construction calls' source text. honest-parse is built; every node
is a real tree-sitter node.

Shape assumption: the scenario names the element a pair "(vocabulary calls, binding
call)" — a 2-element pair whose first member is a collection of vocabulary call
nodes and whose second is the one binding call node. The probe reads pair[0] as an
iterable of nodes and pair[1] as a node, then compares by `.text`. The outer
collection and the vocabulary-list type are not fixed by the scenario. See GAPS.
"""

from honest_parse import parse, walk


def _ctx(src):
    root = parse(src.encode(), "python").root_node
    return {
        "root": root,
        "nodes": walk(root),
        "aliases": {},
        "roles": {},
        "source": src.encode(),
        "path": "probe.py",
        "rule_config": {"HC-OR003": {"min_run": 3}},
    }


# classify(tokens, v, bind=b): positional 2 (v) pairs with the bind keyword (b),
# the one vocab as the vocabulary list.
_CLASSIFY_DECLARATIONS = (
    'v = vocabulary({"int": is_int})\n'
    'b = binding({"int": "slot"})\n'
)
_SRC_CLASSIFY = _CLASSIFY_DECLARATIONS + "classify(tokens, v, bind=b)\n"
_EXPECT_CLASSIFY = {
    (frozenset({'vocabulary({"int": is_int})'}), 'binding({"int": "slot"})'),
}

# link(accepts=v, emits=e, bind=b): both keyword vocabularies pair with the binding.
_SRC_LINK = (
    'v = vocabulary({"a": p})\n'
    'e = vocabulary({"b": q})\n'
    'b = binding({"a": "s"})\n'
    "link(accepts=v, emits=e, bind=b)\n"
)
_EXPECT_LINK = {
    (
        frozenset({'vocabulary({"a": p})', 'vocabulary({"b": q})'}),
        'binding({"a": "s"})',
    ),
}

_CASES = [
    {"src": _SRC_CLASSIFY, "expect": _EXPECT_CLASSIFY},
    {"src": _SRC_LINK, "expect": _EXPECT_LINK},
    {
        "src": _SRC_CLASSIFY + "classify(tokens, v, bind=missing)\n",
        "expect": _EXPECT_CLASSIFY,
    },
    {
        "src": _SRC_CLASSIFY + "classify(tokens, missing, bind=b)\n",
        "expect": _EXPECT_CLASSIFY,
    },
    {
        "src": _SRC_CLASSIFY + "classify(tokens, v.child, bind=b)\n",
        "expect": _EXPECT_CLASSIFY,
    },
    {
        "src": _CLASSIFY_DECLARATIONS + "link(accepts=v, bind=b)\n",
        "expect": _EXPECT_CLASSIFY,
    },
    {
        "src": _SRC_CLASSIFY + "link(bind=b)\n",
        "expect": _EXPECT_CLASSIFY,
    },
    {
        "src": _SRC_CLASSIFY + "link(accepts=v, bind=missing)\n",
        "expect": _EXPECT_CLASSIFY,
    },
]


def _text(node):
    return node.text.decode() if hasattr(node, "text") else repr(node)


def _normalise(pairs):
    out = set()
    for pair in pairs:
        vocab_calls, binding_call = pair[0], pair[1]
        if hasattr(vocab_calls, "type"):  # a single node, not a collection
            vocab_texts = frozenset({_text(vocab_calls)})
        else:
            vocab_texts = frozenset(_text(n) for n in vocab_calls)
        out.add((vocab_texts, _text(binding_call)))
    return out


def probe_vocabulary_binding_pairs():
    """vocabulary_binding_pairs pairs each classify/link's vocabulary calls with its binding call."""
    try:
        from honest_check import vocabulary_binding_pairs
    except ImportError as exc:
        return [f"cannot import vocabulary_binding_pairs: {exc}"]

    bad = []
    for case in _CASES:
        ctx = _ctx(case["src"])
        got = _normalise(vocabulary_binding_pairs(ctx))
        if got != case["expect"]:
            bad.append(
                f"vocabulary_binding_pairs(<module>) -> {got}, expected {case['expect']}"
            )
    return bad
