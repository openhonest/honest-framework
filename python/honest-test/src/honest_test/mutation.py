"""Mutation adequacy (spec section 9.6).

mutate_source produces one Mutant per mechanical change over parseable source, or a Fault when
the source does not parse — it never runs a mutant, because an infinite-loop mutant must not run
inline. classify_mutant_result judges one mutant run against the baseline from the outputs the
memory-capped harness recorded. Both pure. The per-node-type mutant builders are local to
mutate_source, the one declared function that owns them, dispatched through a table keyed by
tree-sitter node type.
"""

import honest_parse

from honest_test._util import _choose, _pick, _read_or
from honest_test.generators import parse_source
from honest_test.support import _fault

# Comparison and boolean swaps and the constant swaps (spec section 9.6 table). Each tree-sitter
# operator node's type is the operator literal, so the key is the node type.
_COMPARISON_SWAP = {"<": "<=", "<=": "<", ">": ">=", ">=": ">", "==": "!=", "!=": "=="}
_BOOLEAN_SWAP = {"and": "or", "or": "and"}
_CONSTANT_SWAP = {"True": "False", "False": "True", "true": "false", "false": "true"}
_MEMBERSHIP_SWAP = {"in": "not in", "not in": "in"}
_RESULT_SWAP = {"ok": "err", "err": "ok"}


def mutate_source(source):
    """Generate every mechanical mutant of a module's source (spec section 9.6), one Mutant per
    change over parseable source, or a Fault when the source does not parse. Reads no world."""
    root = parse_source(source)

    def one(node, change_kind, original, replacement):
        return {
            "location": f"{node.start_point}-{node.end_point}",
            "change_kind": change_kind,
            "original": original,
            "replacement": replacement,
        }

    def comparisons(node):
        swappable = filter(lambda child: child.type in _COMPARISON_SWAP, node.children)
        return [one(child, "comparison_swap", child.type, _COMPARISON_SWAP[child.type])
                for child in swappable]

    def is_simple_number(text):
        core = _choose(text.startswith("-"), text[1:], text)
        return core.isdigit() or (core.count(".") == 1 and core.replace(".", "", 1).isdigit())

    def number_mutants(node, text):
        is_float = "." in text
        value = _pick(is_float, lambda: float(text), lambda: int(text))
        increment = _pick(is_float, lambda: repr(value + 1), lambda: str(value + 1))
        decrement = _pick(is_float, lambda: repr(value - 1), lambda: str(value - 1))
        return [one(node, "number_shift", text, increment),
                one(node, "number_shift", text, decrement)]

    def numbers(node):
        text = node.text.decode("utf-8")
        return _pick(is_simple_number(text), lambda: number_mutants(node, text), lambda: [])

    def booleans(node):
        swappable = filter(lambda child: child.type in _BOOLEAN_SWAP, node.children)
        return [one(child, "condition_flip", child.type, _BOOLEAN_SWAP[child.type])
                for child in swappable]

    def negations(node):
        text = node.text.decode("utf-8")
        stripped = _choose(text.startswith("not"), text[len("not"):].lstrip(), text)
        return [one(node, "condition_flip", text, stripped)]

    def result_mutants(node, function):
        name = function.text.decode("utf-8")
        swap = _read_or(_RESULT_SWAP, name, None)
        original = node.text.decode("utf-8")
        return _pick(
            swap is None,
            lambda: [],
            lambda: [one(node, "result_swap", original, swap + original[len(name):])],
        )

    def results(node):
        function = node.child_by_field_name("function")
        valid = function is not None and function.type == "identifier"
        return _pick(valid, lambda: result_mutants(node, function), lambda: [])

    def keyword_constants(node):
        text = node.text.decode("utf-8")
        swap = _read_or(_CONSTANT_SWAP, text, None)
        return _pick(swap is None, lambda: [], lambda: [one(node, "constant_replace", text, swap)])

    def strings(node):
        text = node.text.decode("utf-8")
        has_quote = bool(text) and text[0] in ("'", '"')
        quote = _pick(has_quote, lambda: text[0], lambda: '"')
        emptied = quote + quote
        return _pick(text != emptied,
                     lambda: [one(node, "constant_replace", text, emptied)],
                     lambda: [])

    def memberships(node):
        swap = _read_or(_MEMBERSHIP_SWAP, node.type, None)
        return _pick(swap is None, lambda: [],
                     lambda: [one(node, "membership_change", node.type, swap)])

    builders = {
        "comparison_operator": comparisons,
        "integer": numbers,
        "float": numbers,
        "boolean_operator": booleans,
        "not_operator": negations,
        "call": results,
        "true": keyword_constants,
        "false": keyword_constants,
        "string": strings,
        "in": memberships,
    }

    def collect():
        mutants = []
        for node in honest_parse.walk(root):
            build = _read_or(builders, node.type, None)
            _pick(build is not None, lambda: mutants.extend(build(node)), lambda: None)
        return mutants

    return _pick(
        root.has_error,
        lambda: _fault(
            "the source handed to the mutation engine is not parseable",
            "fix the source so tree-sitter can parse it before measuring mutation adequacy",
        ),
        lambda: collect(),
    )


def _classify_completed(baseline_output, mutant_output):
    """The completed arm of classify_mutant_result (spec section 9.6): set_aside when the mutant's
    output matches the baseline, caught when a case failed."""
    return _pick(
        mutant_output == baseline_output,
        lambda: {"verdict": "set_aside", "reason": "the change left the suite's observed output identical"},
        lambda: {"verdict": "caught", "reason": ""},
    )


def classify_mutant_result(baseline_output, mutant_output, completed):
    """Judge one mutant run against the baseline (spec section 9.6): undecided when the run did
    not complete, set_aside when the output is identical, caught when a case failed. Reads no
    world, returns pure data."""
    return _pick(
        not completed,
        lambda: {"verdict": "undecided", "reason": "the run hit its time or memory bound and produced no verdict"},
        lambda: _classify_completed(baseline_output, mutant_output),
    )
