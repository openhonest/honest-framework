"""Predicate classification (section 2).

Before generating test cases for a predicate recognizer, honest-test classifies it by its
AST: the class determines the generation strategy (numeric -> Fibonacci, length-bounded ->
enumerate lengths, character-class -> enumerate classes, external -> programmer-supplied,
composite -> recurse into the callee). A predicate that cannot be analysed is treated as
external (supplied-values) - the safe fallback.

The AST work is pure (`classify_source`); the only impure step is reading a live function's
source, isolated in the `classify_predicate` boundary. Parsing goes through honest-parse, the
framework's single tree-sitter boundary.
"""

import inspect

from honest_parse import node_text, parse_python, walk

_CHARCLASS_METHODS = frozenset(
    {
        "isdigit", "isalpha", "isupper", "islower", "isalnum", "isspace",
        "isnumeric", "isdecimal", "isidentifier", "istitle", "isprintable", "isascii",
    }
)

# Named builtins that map directly to a fact. Anything else called by bare name is a
# user/library function (composite or external).
_BUILTIN_FACT = {
    "int": "numeric_call",
    "float": "numeric_call",
    "len": "len_call",
    "isinstance": "catchall",
    "bool": "catchall",
    "type": "catchall",
}

# Builtins that carry no classification signal; calling them does not make a predicate
# composite/external.
_IGNORED_BUILTINS = frozenset(
    {"str", "repr", "abs", "ord", "round", "hex", "oct", "bin", "chr", "min", "max", "sum"}
)

# Precedence of the self-contained classes: the most specific marker wins. A predicate that
# mixes markers (len + isdigit) is classified by the first match here; the universal
# supplied-values fallback covers anything a single strategy cannot fully generate.
_PRECEDENCE = (
    ("character_class", "charclass"),
    ("length", "len_call"),
    ("numeric", "numeric"),
    ("catch_all", "catchall"),
)


def _callee_identifier(callee, source, facts):
    name = node_text(callee, source)
    key = _BUILTIN_FACT.get(name)
    if key is not None:
        facts[key] = True
        return
    if name not in _IGNORED_BUILTINS:
        facts["named_calls"].add(name)


def _callee_attribute(callee, source, facts):
    attribute = callee.child_by_field_name("attribute")
    if attribute is not None and node_text(attribute, source) in _CHARCLASS_METHODS:
        facts["charclass"] = True


_CALLEE = {"identifier": _callee_identifier, "attribute": _callee_attribute}


def _fact_call(node, source, facts):
    callee = node.child_by_field_name("function")
    if callee is None:
        return
    handle = _CALLEE.get(callee.type)
    if handle is not None:
        handle(callee, source, facts)


def _fact_comparison(node, source, facts):
    facts["has_comparison"] = True


def _fact_numeric_literal(node, source, facts):
    facts["has_numlit"] = True


def _fact_true(node, source, facts):
    facts["catchall"] = True


_NODE_FACT = {
    "call": _fact_call,
    "comparison_operator": _fact_comparison,
    "integer": _fact_numeric_literal,
    "float": _fact_numeric_literal,
    "true": _fact_true,
}


def _collect_facts(source):
    facts = {
        "charclass": False,
        "len_call": False,
        "numeric_call": False,
        "has_comparison": False,
        "has_numlit": False,
        "catchall": False,
        "named_calls": set(),
    }
    source_bytes = source.encode("utf-8")
    root = parse_python(source_bytes).root_node
    for node in walk(root):
        handle = _NODE_FACT.get(node.type)
        if handle is not None:
            handle(node, source_bytes, facts)
    facts["numeric"] = facts["numeric_call"] or (facts["has_comparison"] and facts["has_numlit"])
    return facts


def classify_source(source, codebase_names=None):
    """Classify a predicate from its source text (pure). Returns one of: character_class,
    length, numeric, catch_all, composite, external, unknown (section 2)."""
    facts = _collect_facts(source)
    for class_name, key in _PRECEDENCE:
        if facts[key]:
            return class_name
    if facts["named_calls"]:
        name = sorted(facts["named_calls"])[0]
        return "composite" if codebase_names and name in codebase_names else "external"
    return "unknown"


# honest: disable HC-P002: a predicate that raises is reported as a failed predicate, not propagated
def classify_predicate(predicate_or_fn, codebase_names=None):
    """Classify a live predicate recognizer or callable (section 2). Reads the function's
    source - the one impure step - and delegates to classify_source. A function whose source
    cannot be read (C-defined, dynamically built) is unanalysable, so it is treated as
    external (supplied-values)."""
    fn = predicate_or_fn["fn"] if hasattr(predicate_or_fn, "get") else predicate_or_fn
    try:
        source = inspect.getsource(fn)
    except (OSError, TypeError):
        return "external"
    return classify_source(source, codebase_names)
# honest: enable HC-P002
