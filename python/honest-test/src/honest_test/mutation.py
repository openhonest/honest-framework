"""Mutation adequacy (spec section 9.6).

mutate_source produces one Mutant per mechanical change over parseable source, or a Fault when
the source does not parse — it never runs a mutant, because an infinite-loop mutant must not run
inline. classify_mutant_result judges one mutant run against the baseline from the outputs the
memory-capped harness recorded. Both pure. The per-node-type mutant builders are local to
mutate_source, the one declared function that owns them, dispatched through a table keyed by
tree-sitter node type.
"""

import honest_parse

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
    if root.has_error:
        return _fault(
            "the source handed to the mutation engine is not parseable",
            "fix the source so tree-sitter can parse it before measuring mutation adequacy",
        )

    def one(node, change_kind, original, replacement):
        return {
            "location": f"{node.start_point}-{node.end_point}",
            "change_kind": change_kind,
            "original": original,
            "replacement": replacement,
        }

    def comparisons(node):
        return [one(child, "comparison_swap", child.type, _COMPARISON_SWAP[child.type])
                for child in node.children if child.type in _COMPARISON_SWAP]

    def is_simple_number(text):
        core = text[1:] if text.startswith("-") else text
        return core.isdigit() or (core.count(".") == 1 and core.replace(".", "", 1).isdigit())

    def numbers(node):
        text = node.text.decode("utf-8")
        if not is_simple_number(text):
            return []
        value = float(text) if "." in text else int(text)
        increment = repr(value + 1) if "." in text else str(value + 1)
        decrement = repr(value - 1) if "." in text else str(value - 1)
        return [one(node, "number_shift", text, increment), one(node, "number_shift", text, decrement)]

    def booleans(node):
        return [one(child, "condition_flip", child.type, _BOOLEAN_SWAP[child.type])
                for child in node.children if child.type in _BOOLEAN_SWAP]

    def negations(node):
        text = node.text.decode("utf-8")
        stripped = text[len("not"):].lstrip() if text.startswith("not") else text
        return [one(node, "condition_flip", text, stripped)]

    def results(node):
        function = node.child_by_field_name("function")
        if function is None or function.type != "identifier":
            return []
        name = function.text.decode("utf-8")
        if name not in _RESULT_SWAP:
            return []
        original = node.text.decode("utf-8")
        return [one(node, "result_swap", original, _RESULT_SWAP[name] + original[len(name):])]

    def keyword_constants(node):
        text = node.text.decode("utf-8")
        return [one(node, "constant_replace", text, _CONSTANT_SWAP[text])] if text in _CONSTANT_SWAP else []

    def strings(node):
        text = node.text.decode("utf-8")
        quote = text[0] if text and text[0] in ("'", '"') else '"'
        emptied = quote + quote
        return [one(node, "constant_replace", text, emptied)] if text != emptied else []

    def memberships(node):
        return [one(node, "membership_change", node.type, _MEMBERSHIP_SWAP[node.type])] if node.type in _MEMBERSHIP_SWAP else []

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

    mutants = []
    for node in honest_parse.walk(root):
        build = builders.get(node.type)
        if build is not None:
            mutants.extend(build(node))
    return mutants


def classify_mutant_result(baseline_output, mutant_output, completed):
    """Judge one mutant run against the baseline (spec section 9.6): undecided when the run did
    not complete, set_aside when the output is identical, caught when a case failed. Reads no
    world, returns pure data."""
    if not completed:
        return {"verdict": "undecided", "reason": "the run hit its time or memory bound and produced no verdict"}
    if mutant_output == baseline_output:
        return {"verdict": "set_aside", "reason": "the change left the suite's observed output identical"}
    return {"verdict": "caught", "reason": ""}
