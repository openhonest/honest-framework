"""honest-check AST helper layer: bindings (split from core.py for L1.17).

Each helper takes the check context ctx (root, nodes, aliases, roles, source, path, rule_config)
and returns data; the rule logic that uses them stays nested-as-data in the sub-cores (section 3.4)."""

from honest_check.nodes import base_types_of, call_arguments, canonical_name, literal_string
from honest_check.analysis import construction_maps


def vocabulary_types(ctx, vocab_call):
    """The type surface of a `vocabulary(...)` call: its base-type names, its composed-type
    names, the base names its composed types require, and the base names its composed types
    capture (§HC004, §HC005). base_types_of reads the first-argument dictionary's keys; the
    composed data is read from each `composed(name, requires, captures)` call in the
    `composed_types` keyword, the same shape check_composed reads."""
    positionals, keywords = call_arguments(ctx, vocab_call)
    base_names = set()
    if positionals and positionals[0].type == "dictionary":
        base_names = set(base_types_of(ctx, positionals[0]))
    composed_names = set()
    composed_requires = set()
    composed_captures = set()
    composed_list = keywords.get("composed_types")
    if composed_list is not None:
        for child in composed_list.named_children:
            if child.type != "call" or canonical_name(ctx, child) != "composed":
                continue
            c_positionals, _c_keywords = call_arguments(ctx, child)
            if c_positionals and c_positionals[0].type == "string":
                composed_names.add(literal_string(c_positionals[0]))
            if len(c_positionals) >= 2 and c_positionals[1].type == "dictionary":
                for pair in c_positionals[1].named_children:
                    if pair.type == "pair":
                        composed_requires.add(
                            literal_string(pair.child_by_field_name("key"))
                        )
            if len(c_positionals) >= 3 and c_positionals[2].type == "string":
                composed_captures.add(literal_string(c_positionals[2]))
    return base_names, composed_names, composed_requires, composed_captures


def binding_keys(ctx, binding_call):
    """The type names a `binding(...)` call binds — the keys of its first-argument table
    (§HC004, §HC005)."""
    positionals, _keywords = call_arguments(ctx, binding_call)
    if not positionals or positionals[0].type != "dictionary":
        return set()
    keys = set()
    for pair in positionals[0].named_children:
        if pair.type == "pair":
            keys.add(literal_string(pair.child_by_field_name("key")))
    return keys


def vocabulary_binding_pairs(ctx):
    """Each (vocabulary calls, binding call) a classify or link pairs by name (§HC004,
    §HC005). A `classify(tokens, vocab, bind=b)` pairs positional 2 with the `bind`
    keyword, and its vocabulary list is the one vocab. A `link(accepts=v, emits=e, binds=b)`
    (bare or as a decorator) pairs `accepts` with `binds`, and its binding legitimately
    spans both the types it accepts and the types it emits, so its vocabulary list is
    `accepts` followed by `emits` when `emits` resolves — the binding is crossed against the
    union of both. A link with no `emits` keyword, or an `emits` that resolves to no local
    vocabulary, lists `accepts` alone, so it behaves as the union with the empty set. A site
    with no binding keyword uses the identity auto_binding, which binds each type to itself,
    so neither rule fires and the site is not a pair. A vocabulary or binding argument that
    is not a plain name, or a name that resolves to no local construction, is skipped —
    honest-check cannot cross what it was not handed. A pair reached from two sites is
    crossed once."""
    nodes = ctx["nodes"]
    vocab_calls, binding_calls = construction_maps(ctx)
    pairs = []
    seen = set()
    for node in nodes:
        if node.type != "call":
            continue
        canonical = canonical_name(ctx, node)
        positionals, keywords = call_arguments(ctx, node)
        if canonical == "classify":
            vocab_arg = positionals[1] if len(positionals) >= 2 else None
            emits_arg = None
            binding_arg = keywords.get("bind")
        elif canonical == "link":
            vocab_arg = keywords.get("accepts")
            emits_arg = keywords.get("emits")
            binding_arg = keywords.get("binds")
        else:
            continue
        if binding_arg is None:
            continue
        if (
            vocab_arg is None
            or vocab_arg.type != "identifier"
            or binding_arg.type != "identifier"
        ):
            continue
        vocab_call = vocab_calls.get(vocab_arg.text.decode("utf-8"))
        binding_call = binding_calls.get(binding_arg.text.decode("utf-8"))
        if vocab_call is None or binding_call is None:
            continue
        resolved = [vocab_call]
        if emits_arg is not None and emits_arg.type == "identifier":
            emits_call = vocab_calls.get(emits_arg.text.decode("utf-8"))
            if emits_call is not None:
                resolved.append(emits_call)
        key = (tuple(id(call) for call in resolved), id(binding_call))
        if key in seen:
            continue
        seen.add(key)
        pairs.append((resolved, binding_call))
    return pairs
