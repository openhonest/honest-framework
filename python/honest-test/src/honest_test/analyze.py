"""Source analysis: parse, find predicates, classify them, and the source-decidable
generators (length and numeric), plus mutation generation and its verdict (spec
sections 2, 3.3, 3.4, 3.6, 9.6). Every declared function here is pure.

The private AST readers below are module-level lambdas, not column-0 `def`s, so the
module's column-0 functions are exactly the nine the .hd declares; each declared
function keeps its own one gherkin scenario and nothing else does. Function-specific
multi-statement helpers nest inside the one function that uses them.
"""

from honest_parse import parse, walk

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
_integer_operands = lambda comparison: list(filter(lambda c: c.type == "integer", comparison.named_children))
_has_numeric_comparison = lambda node: next(filter(lambda c: len(_integer_operands(c)) > 0 and "len" not in _simple_call_names(c), _comparisons(node)), None) is not None
_len_comparison = lambda node: next(filter(lambda c: "len" in _simple_call_names(c), _comparisons(node)), None)
_comparison_tokens = lambda comparison: [_choose("len" in _simple_call_names(child), "LEN", child.text.decode("utf-8")) for child in comparison.children]
_string_at = lambda n: (_CHARS * ((n // len(_CHARS)) + 1))[:n]
_location = lambda node: f"{node.start_point}-{node.end_point}"
_mutant = lambda node, change_kind, replacement: {"location": _location(node), "change_kind": change_kind, "original": node.text.decode("utf-8"), "replacement": replacement}


def parse_source(source):
    """Parse one source file's text with tree-sitter and return the root node (sections
    2, 9.6). tree-sitter builds error nodes for malformed input rather than failing, so
    this returns a node, never a fault."""
    return parse(source.encode("utf-8"), "python").root_node


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


def classify_predicate(predicate_node):
    """Sort one predicate into its generation class from its AST (section 2): a len(s)
    comparison is length_bounded, an is-method call is character_class, an int()/float()
    call or a numeric comparison is numeric. A call the single node cannot locate in the
    codebase falls to external_lookup, the safe default."""
    markers = {
        "length_bounded": "len" in _simple_call_names(predicate_node),
        "character_class": len(_method_names(predicate_node) & _CHAR_METHODS) > 0,
        "numeric": len(_simple_call_names(predicate_node) & {"int", "float"}) > 0 or _has_numeric_comparison(predicate_node),
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


def mutate_source(source):
    """Generate every mechanical mutant of a module's source for the adequacy measure
    (section 9.6), one Mutant per place each of the seven change kinds fits. Returns a
    Fault when the source does not parse, because a mutant can only be made from parseable
    source."""
    def _comparison_mutants(root):
        operators = filter(lambda n: n.type in _SWAP, walk(root))
        return [_mutant(op, "comparison_swap", _SWAP[op.type]) for op in operators]

    def _number_mutants(root):
        integers = filter(lambda n: n.type == "integer", walk(root))
        return [_mutant(n, "number_shift", str(int(n.text.decode("utf-8")) + 1)) for n in integers]

    def _boolean_mutants(root):
        flip = {"and": "or", "or": "and"}
        text_of = lambda node: next(map(lambda c: c.type, filter(lambda c: c.type in ("and", "or"), node.children)), "")
        operators = filter(lambda n: n.type == "boolean_operator", walk(root))
        flippable = filter(lambda op: _read_or(flip, text_of(op), None) is not None, operators)
        return [_mutant(op, "condition_flip", flip[text_of(op)]) for op in flippable]

    def _constant_mutants(root):
        literals = filter(lambda n: n.type in ("true", "false", "integer"), walk(root))
        replaceable = filter(lambda n: _read_or(_CONSTANTS, n.text.decode("utf-8"), None) is not None, literals)
        strings = filter(lambda n: n.type == "string", walk(root))
        return [_mutant(n, "constant_replace", _CONSTANTS[n.text.decode("utf-8")]) for n in replaceable] + [_mutant(s, "constant_replace", '""') for s in strings]

    def _membership_mutants(root):
        operators = filter(lambda n: n.type == "comparison_operator", walk(root))
        has_in = filter(lambda c: any(ch.type == "in" for ch in c.children), operators)
        return [_mutant(c, "membership_change", c.text.decode("utf-8").replace(" in ", " not in ", 1)) for c in has_in]

    def _all_mutants(root):
        return _comparison_mutants(root) + _number_mutants(root) + _boolean_mutants(root) + _constant_mutants(root) + _membership_mutants(root)

    root = parse(source.encode("utf-8"), "python").root_node
    return _pick(
        root.has_error,
        lambda: {
            "problem": "the module source handed to the mutation engine does not parse",
            "remedy": "fix the source so tree-sitter can parse it, then regenerate the mutants",
        },
        lambda: _all_mutants(root),
    )


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
