"""Source analysis: parse, find predicates, classify them, and the source-decidable
generators (length and numeric), plus mutation generation and its verdict (spec
sections 2, 3.3, 3.4, 3.6, 9.6). Every declared function here is pure.

The private AST readers below are module-level lambdas, not column-0 `def`s, so the
module's column-0 functions are exactly the nine the .hd declares; each declared
function keeps its own one gherkin scenario and nothing else does. Function-specific
multi-statement helpers nest inside the one function that uses them.
"""

from honest_parse import parse_root_node, walk

from honest_test._util import _choose, _pick, _read_or

_CHARS = "abcdefghijklmnopqrstuvwxyz0123456789"
_SWAP = {"<": "<=", ">": ">=", "==": "!=", "<=": "<", ">=": ">", "!=": "=="}
_CONSTANTS = {"0": "1", "1": "0", "True": "False", "False": "True"}
_CHAR_METHODS = {"isdigit", "isalpha", "isupper", "islower", "isalnum"}

_calls_in = lambda node: list(filter(lambda n: n.type == "call", walk(node)))
_call_functions = lambda node: list(filter(lambda f: f is not None, map(lambda c: c.child_by_field_name("function"), _calls_in(node))))
_simple_call_names = lambda node: set(f.text.decode("utf-8") for f in filter(lambda f: f.type == "identifier", _call_functions(node)))
_method_names = lambda node: set(f.child_by_field_name("attribute").text.decode("utf-8") for f in filter(lambda f: f.type == "attribute", _call_functions(node)))
_comparisons = lambda node: list(filter(lambda n: n.type == "comparison_operator", walk(node)))
_len_comparison = lambda node: next(filter(lambda c: "len" in _simple_call_names(c), _comparisons(node)), None)
_comparison_tokens = lambda comparison: [_choose("len" in _simple_call_names(child), "LEN", child.text.decode("utf-8")) for child in comparison.children]
_string_at = lambda n: (_CHARS * ((n // len(_CHARS)) + 1))[:n]
_location = lambda node: f"{node.start_point}-{node.end_point}"
_mutant = lambda node, change_kind, replacement: {"location": _location(node), "change_kind": change_kind, "original": node.text.decode("utf-8"), "replacement": replacement}


# inherits: hd=python/honest-test/honest-test.hd::parse_source -> feature=specs/features/honest-test.feature::parse_source returns a recovered Python root for malformed source -> test=python/honest-test/conformance/probe_parse_source_recovery.py::probe_parse_source_recovery
# inherits: hd=python/honest-test/honest-test.hd::parse_source -> feature=specs/features/honest-test.feature::parse_source returns a Python root for UTF-8 source -> test=python/honest-test/conformance/probe_parse_source_utf8.py::probe_parse_source_utf8
# inherits: hd=python/honest-test/honest-test.hd::parse_source -> feature=specs/features/honest-test.feature::parse_source parses one source file with tree-sitter -> test=python/honest-test/conformance/probe_parse_source.py::probe_parse_source
# hd: parse_source
def parse_source(source):
    """Parse one source file's text with tree-sitter and return the root node (sections
    2, 9.6). tree-sitter builds error nodes for malformed input rather than failing, so
    this returns a node, never a fault."""
    return parse_root_node(source.encode("utf-8"), "python")


def extract_predicates(tree):
    """Return the function_definition node of each @recognizer-marked predicate (section
    2). A plain function and a @link are not recognizers and are excluded; a file with no
    recognizer yields the empty list."""
    def _decorator_names(decorated):
        decorators = filter(lambda c: c.type == "decorator", decorated.children)
        targets = map(lambda d: next(filter(lambda n: n.type in ("identifier", "call", "attribute"), d.children), None), decorators)
        return set(n.text.decode("utf-8") for n in filter(lambda n: n is not None, targets))

    decorated = filter(lambda n: n.type == "decorated_definition", walk(tree))
    recognizers = filter(lambda d: "recognizer" in _decorator_names(d), decorated)
    bodies = map(lambda d: next(filter(lambda c: c.type == "function_definition", d.children), None), recognizers)
    return list(filter(lambda n: n is not None, bodies))


# inherits: hd=python/honest-test/honest-test-pure.hd::classify_predicate -> feature=specs/features/honest-test.feature::classify_predicate selects generation classes for declared syntax markers -> test=python/honest-test/conformance/probe_classify_predicate_declared_markers.py::probe_classify_predicate_declared_markers
# hd: classify_predicate
def classify_predicate(predicate_node):
    """Sort one predicate into its generation class from its AST (section 2): a len(s)
    comparison is length_bounded, an is-method call is character_class, an int()/float()
    call or a numeric comparison is numeric. A call the single node cannot locate in the
    codebase falls to external_lookup, the safe default."""
    call_names = _simple_call_names(predicate_node)
    numeric = bool(call_names & {"int", "float"}) or any(
        any(operand.type in {"integer", "float"} for operand in comparison.named_children)
        and "len" not in _simple_call_names(comparison)
        for comparison in _comparisons(predicate_node)
    )
    markers = {
        "length_bounded": "len" in call_names,
        "character_class": len(_method_names(predicate_node) & _CHAR_METHODS) > 0,
        "numeric": numeric,
    }
    order = ("length_bounded", "character_class", "numeric")
    hit = next(filter(lambda name: markers[name], order), None)
    return _pick(hit is None, lambda: "external_lookup", lambda: hit)


def enumerate_lengths(predicate_node):
    """Generate the strings for a length-bounded predicate (section 3.4): one valid string
    at every length in the range, and the invalid boundary lengths just outside — one over
    the maximum always, one under the minimum when the minimum exceeds one. A pure lower
    bound with no maximum generates nothing here."""
    def _lower_from(before):
        has = len(before) >= 2
        table = {"<=": lambda value: value, "<": lambda value: value + 1}
        reader = _pick(has, lambda: _read_or(table, before[-1], None), lambda: None)
        return _pick(reader is None, lambda: 1, lambda: reader(int(before[-2])))

    def _upper_from(after):
        has = len(after) >= 2
        table = {
            "==": lambda value: ("eq", value),
            "<=": lambda value: ("max", value),
            "<": lambda value: ("max", value - 1),
            ">=": lambda value: ("min", value),
            ">": lambda value: ("min", value + 1),
        }
        reader = _pick(has, lambda: _read_or(table, after[0], None), lambda: None)
        return _pick(reader is None, lambda: ("none", 0), lambda: reader(int(after[1])))

    def _range_cases(low, high):
        valid = [_string_at(n) for n in range(low, high + 1)]
        under = _choose(low > 1, [_string_at(low - 1)], [])
        return {"valid": valid, "invalid": [_string_at(high + 1)] + under}

    def _from_comparison(comparison):
        tokens = _comparison_tokens(comparison)
        position = tokens.index("LEN")
        lower = _lower_from(tokens[:position])
        kind, upper = _upper_from(tokens[position + 1:])
        resolved = {"eq": (upper, upper), "max": (lower, upper), "min": (upper, None), "none": (lower, None)}
        low, high = _read_or(resolved, kind, (lower, None))
        return _pick(high is None, lambda: {"valid": [], "invalid": []}, lambda: _range_cases(low, high))

    comparison = _len_comparison(predicate_node)
    return _pick(comparison is None, lambda: {"valid": [], "invalid": []}, lambda: _from_comparison(comparison))


def fibonacci_sequence(limit, negative):
    """The Fibonacci probe values from zero up to limit (section 3.3): the negatives of the
    strictly-positive terms, then the non-negative sequence, when negative is true; the
    non-negative sequence alone otherwise."""
    seq = [0, 1]
    while seq[-1] < limit:
        seq.append(seq[-1] + seq[-2])
    negatives = [-value for value in filter(lambda v: v > 0, seq)]
    return _choose(negative, negatives + seq, list(seq))


def supplied_cases(predicate_name, supplied_values):
    """Resolve one predicate's programmer-supplied values from the config (section 3.6).
    A present entry yields its valid and invalid lists with missing false; an absent one
    yields empty lists with missing true — the missing_supplied_values warning case."""
    entry = _read_or(supplied_values, predicate_name, None)
    return _pick(
        entry is None,
        lambda: {"valid": [], "invalid": [], "missing": True},
        lambda: {"valid": entry["valid"], "invalid": entry["invalid"], "missing": False},
    )


def resolve_supplied_config(table):
    """Reshape the decoded honest-test.toml table into a SuppliedConfig (sections 3.6, 10):
    a map from each predicate name under [predicates] to its SuppliedEntry. Non-predicate
    sections do not leak in; a table declaring no predicates resolves to the empty map."""
    def _entry(config):
        return {
            "valid": _read_or(config, "valid", []),
            "invalid": _read_or(config, "invalid", []),
            "strategy": _read_or(config, "strategy", "supplied_only"),
        }

    predicates = _read_or(table, "predicates", {})
    return {name: _entry(config) for name, config in predicates.items()}


# inherits: hd=python/honest-test/honest-test.hd::_number_mutants -> feature=specs/features/honest-test.feature::_number_mutants shifts hexadecimal octal and binary tokens -> test=python/honest-test/conformance/probe_number_mutants_bases.py::run
# inherits: hd=python/honest-test/honest-test.hd::_number_mutants -> feature=specs/features/honest-test.feature::_number_mutants keeps decimal token spans separate from unary signs -> test=python/honest-test/conformance/probe_number_mutants_decimal.py::run
# inherits: hd=python/honest-test/honest-test.hd::_number_mutants -> feature=specs/features/honest-test.feature::_number_mutants skips imaginary tokens and preserves integer order -> test=python/honest-test/conformance/probe_number_mutants_imaginary.py::run
# hd: _number_mutants
def _number_mutants(root):
    """Shift real integer tokens by one while preserving their text and locations."""
    integers = filter(lambda node: node.type == "integer", walk(root))
    tokens = ((node, node.text.decode("utf-8")) for node in integers)
    real_integers = filter(lambda item: not item[1].endswith(("j", "J")), tokens)
    mutants = []
    for node, token in real_integers:
        base = _choose(token[:2].lower() in ("0x", "0o", "0b"), 0, 10)
        mutants.append(_mutant(node, "number_shift", str(int(token, base) + 1)))
    return mutants


# inherits: hd=python/honest-test/honest-test.hd::_boolean_mutants -> feature=specs/features/honest-test.feature::_boolean_mutants flips only operator tokens in source order -> test=python/honest-test/conformance/probe_boolean_mutants_operator_tokens.py::probe_boolean_mutants_operator_tokens
# inherits: hd=python/honest-test/honest-test.hd::_boolean_mutants -> feature=specs/features/honest-test.feature::_boolean_mutants returns no flips for operator words in strings and comments -> test=python/honest-test/conformance/probe_boolean_mutants_no_tokens.py::probe_boolean_mutants_no_tokens
# hd: _boolean_mutants
def _boolean_mutants(root):
    """Flip each parsed and/or token without including either operand."""
    flip = {"and": "or", "or": "and"}
    operators = filter(lambda node: node.type in flip, walk(root))
    return [_mutant(operator, "condition_flip", flip[operator.type]) for operator in operators]


# inherits: hd=python/honest-test/honest-test.hd::_membership_mutants -> feature=specs/features/honest-test.feature::_membership_mutants flips each chained membership token independently -> test=python/honest-test/conformance/probe_membership_mutants_chain.py::probe_membership_mutants_chain
# inherits: hd=python/honest-test/honest-test.hd::_membership_mutants -> feature=specs/features/honest-test.feature::_membership_mutants preserves the raw span of a spaced not in token -> test=python/honest-test/conformance/probe_membership_mutants_spaced.py::probe_membership_mutants_spaced
# inherits: hd=python/honest-test/honest-test.hd::_membership_mutants -> feature=specs/features/honest-test.feature::_membership_mutants ignores iterator syntax strings and comments -> test=python/honest-test/conformance/probe_membership_mutants_exclusions.py::probe_membership_mutants_exclusions
# hd: _membership_mutants
def _membership_mutants(root):
    """Flip each membership comparison token at its original span."""
    flip = {"in": "not in", "not in": "in"}
    operators = filter(
        lambda node: node.type in flip and node.parent.type == "comparison_operator",
        walk(root),
    )
    return [_mutant(operator, "membership_change", flip[operator.type]) for operator in operators]


# inherits: hd=python/honest-test/honest-test.hd::source_mutants -> feature=specs/features/honest-test.feature::source_mutants emits separate condition and membership changes in traversal order -> test=python/honest-test/conformance/probe_source_mutants_condition_membership.py::probe_source_mutants_condition_membership
# inherits: hd=python/honest-test/honest-test.hd::source_mutants -> feature=specs/features/honest-test.feature::source_mutants returns a fault for an unparseable root -> test=python/honest-test/conformance/probe_source_mutants_malformed.py::probe_source_mutants_malformed
# inherits: hd=python/honest-test/honest-test.hd::source_mutants -> feature=specs/features/honest-test.feature::source_mutants enumerates the declared mechanical changes -> test=python/honest-test/conformance/probe_source_mutants_mechanical.py::probe_source_mutants_mechanical
# hd: source_mutants
def source_mutants(root):
    """Generate the mechanical mutants of a parsed Python root, or return its parse fault."""
    def _comparison_mutants(root):
        operators = filter(lambda n: n.type in _SWAP, walk(root))
        return [_mutant(op, "comparison_swap", _SWAP[op.type]) for op in operators]

    def _constant_mutants(root):
        literals = filter(lambda n: n.type in ("true", "false", "integer"), walk(root))
        replaceable = filter(lambda n: _read_or(_CONSTANTS, n.text.decode("utf-8"), None) is not None, literals)
        strings = filter(lambda n: n.type == "string", walk(root))
        return [_mutant(n, "constant_replace", _CONSTANTS[n.text.decode("utf-8")]) for n in replaceable] + [_mutant(s, "constant_replace", '""') for s in strings]

    def _all_mutants(root):
        return _comparison_mutants(root) + _number_mutants(root) + _boolean_mutants(root) + _constant_mutants(root) + _membership_mutants(root)

    return _pick(
        root.has_error,
        lambda: {
            "problem": "the module source handed to the mutation engine does not parse",
            "remedy": "fix the source so tree-sitter can parse it, then regenerate the mutants",
        },
        lambda: _all_mutants(root),
    )


# inherits: hd=python/honest-test/honest-test.hd::run_source_mutation -> feature=specs/features/honest-test.feature::run_source_mutation returns a fault for malformed source -> test=python/honest-test/conformance/probe_run_source_mutation_malformed.py::probe_run_source_mutation_malformed
# inherits: hd=python/honest-test/honest-test.hd::run_source_mutation -> feature=specs/features/honest-test.feature::run_source_mutation returns mutants for parseable source -> test=python/honest-test/conformance/probe_run_source_mutation_parseable.py::probe_run_source_mutation_parseable
# hd: run_source_mutation
def run_source_mutation(source):
    """Read the Python root and return its mutation findings."""
    return source_mutants(parse_source(source))


# inherits: hd=python/honest-test/honest-test.hd::mutate_source -> feature=specs/features/honest-test.feature::mutate_source generates every mechanical mutant of the source -> test=python/honest-test/conformance/probe_mutate_source.py::probe_mutate_source
# hd: mutate_source
def mutate_source(source):
    """Return the mutations generated for the supplied source text."""
    return run_source_mutation(source)


def classify_mutant_result(baseline_output, mutant_output, completed):
    """Judge one mutant run against the baseline (section 9.6): undecided when the run did
    not complete within its bound (and undecided dominates), set_aside when the output is
    identical to the baseline, caught when it differs."""
    return _pick(
        not completed,
        lambda: {"verdict": "undecided", "reason": "the mutant run hit its time or memory bound and produced no verdict"},
        lambda: _pick(
            mutant_output == baseline_output,
            lambda: {"verdict": "set_aside", "reason": "the change left the suite's observed output identical to the baseline"},
            lambda: {"verdict": "caught", "reason": ""},
        ),
    )
