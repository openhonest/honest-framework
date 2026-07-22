"""JavaScript mutation gate (section 9.6) — the JavaScript counterpart of python/mutate.py.

Enumerate the mutants of a JavaScript source over the shared tree-sitter grammar, and for each mutant
run the package's Node test suite: a mutant the suite still passes is a survivor. Report adequacy —
caught + set_aside == total, zero undeclared — reusing the language-general accounting
(honest_test.mutation.mutation_adequacy) and label stabiliser (_stabilize_labels).

Operators mirror the section 9.6 set for JavaScript node shapes: comparison swap, logical swap and
`!` removal, number shift, constant emptying, object-key swap, statement removal, and else-arm
removal. result-swap (ok/err) and membership (in) are honest-type / Python constructs and do not apply
to vanilla JavaScript. A per-mutant timeout guards a mutant that spins; a timed-out or crashing mutant
is caught (the suite did not pass). This is the mutation boundary, so it is not itself linted.

  cd python && uv run python ../javascript/js_mutate.py <src-file.js>
"""

import json
import subprocess
import sys
from pathlib import Path

from honest_parse import node_text, parse_javascript, walk
from honest_test.mutation import _stabilize_labels, mutation_adequacy

_PER_MUTANT_TIMEOUT = 30

_COMPARISON_SWAP = {"<": "<=", "<=": "<", ">": ">=", ">=": ">", "===": "!==", "!==": "===", "==": "!=", "!=": "=="}
_LOGICAL_SWAP = {"&&": "||", "||": "&&"}


def _edit(source, start, end, replacement):
    return source[:start] + replacement + source[end:]


def _mutant(operator, label, source, start, end, replacement):
    return {"operator": operator, "label": label, "source": _edit(source, start, end, replacement).decode("utf-8")}


def _binary_operator_swaps(tree, source):
    mutants = []
    for node in walk(tree.root_node):
        if node.type != "binary_expression":
            continue
        op = node.child_by_field_name("operator")
        text = node_text(op, source)
        if text in _COMPARISON_SWAP:
            mutants.append(_mutant("comparison_swap", f"{text}->{_COMPARISON_SWAP[text]}@{op.start_byte}", source, op.start_byte, op.end_byte, _COMPARISON_SWAP[text].encode("utf-8")))
        elif text in _LOGICAL_SWAP:
            mutants.append(_mutant("condition_flip", f"{text}->{_LOGICAL_SWAP[text]}@{op.start_byte}", source, op.start_byte, op.end_byte, _LOGICAL_SWAP[text].encode("utf-8")))
    return mutants


def _not_removals(tree, source):
    mutants = []
    for node in walk(tree.root_node):
        if node.type == "unary_expression" and node_text(node.child_by_field_name("operator"), source) == "!":
            argument = node.child_by_field_name("argument")
            mutants.append(_mutant("condition_flip", f"drop-not@{node.start_byte}", source, node.start_byte, node.end_byte, node_text(argument, source).encode("utf-8")))
    return mutants


def _number_shifts(tree, source):
    mutants = []
    for node in walk(tree.root_node):
        if node.type != "number":
            continue
        text = node_text(node, source)
        if "." in text or ("e" in text.lower() and not text.lower().startswith("0x")):
            value = float(text)
        else:
            value = int(text, 0)
        for shift in (1, -1):
            mutants.append(_mutant("number_shift", f"{value}->{value + shift}@{node.start_byte}", source, node.start_byte, node.end_byte, str(value + shift).encode("utf-8")))
    return mutants


def _constant_empties(tree, source):
    mutants = []
    for node in walk(tree.root_node):
        if node.type != "string":
            continue
        if node.end_byte - node.start_byte <= 2:
            continue  # already empty ("" / '')
        quote = node_text(node, source)[0]
        mutants.append(_mutant("constant_replace", f"string->empty@{node.start_byte}", source, node.start_byte, node.end_byte, f"{quote}{quote}".encode("utf-8")))
    return mutants


def _object_key_swaps(tree, source):
    mutants = []
    for node in walk(tree.root_node):
        if node.type != "object":
            continue
        pairs = [child for child in node.named_children if child.type == "pair"]
        if len(pairs) < 2:
            continue
        keys = [pair.child_by_field_name("key") for pair in pairs]
        for index, key in enumerate(keys):
            replacement = keys[(index + 1) % len(keys)]
            new_text = node_text(replacement, source)
            if new_text == node_text(key, source):
                continue
            mutants.append(_mutant("dict_key_swap", f"key->{new_text}@{key.start_byte}", source, key.start_byte, key.end_byte, new_text.encode("utf-8")))
    return mutants


def _statement_removals(tree, source):
    mutants = []
    for node in walk(tree.root_node):
        if node.type not in ("statement_block", "program"):
            continue
        for statement in [child for child in node.named_children if child.type != "comment"]:
            mutants.append(_mutant("line_removal", f"remove@{statement.start_byte}", source, statement.start_byte, statement.end_byte, b""))
    return mutants


def _else_removals(tree, source):
    mutants = []
    for node in walk(tree.root_node):
        if node.type != "if_statement":
            continue
        alternative = node.child_by_field_name("alternative")
        if alternative is not None:
            mutants.append(_mutant("branch_arm_removal", f"drop-else@{alternative.start_byte}", source, alternative.start_byte, alternative.end_byte, b""))
    return mutants


_OPERATORS = (_binary_operator_swaps, _not_removals, _number_shifts, _constant_empties, _object_key_swaps, _statement_removals, _else_removals)


def enumerate_js_mutants(source):
    source_bytes = source.encode("utf-8")
    tree = parse_javascript(source_bytes)
    mutants = []
    for operator in _OPERATORS:
        mutants.extend(operator(tree, source_bytes))
    return _stabilize_labels(mutants, source, tree, source_bytes)


def _suite_passes(pkg):
    """The Node test suite passes on the source currently on disk. A crash or a timeout is not a pass."""
    try:
        result = subprocess.run(["node", "--test"], cwd=pkg, capture_output=True, timeout=_PER_MUTANT_TIMEOUT)
    except subprocess.TimeoutExpired:
        return False
    return result.returncode == 0


def _set_aside(pkg, relpath):
    path = pkg / "conformance" / "mutants_setaside.json"
    entries = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    return {label[len(relpath) + 1:] for label in entries if label.startswith(relpath + ":")}


def run(src_file):
    src_path = Path(src_file).resolve()
    pkg = src_path.parent.parent
    relpath = src_path.name
    original = src_path.read_text(encoding="utf-8")

    if not _suite_passes(pkg):
        print(f"js-mutate: {relpath} — the test suite does not pass on the unmutated source; fix it before measuring.", file=sys.stderr)
        return 1

    mutants = enumerate_js_mutants(original)
    survivors = []
    try:
        for mutant in mutants:
            src_path.write_text(mutant["source"], encoding="utf-8")
            if _suite_passes(pkg):
                survivors.append(mutant)
    finally:
        src_path.write_text(original, encoding="utf-8")

    report = mutation_adequacy(mutants, survivors, _set_aside(pkg, relpath))
    print(f"js-mutate: {relpath} — {report['caught']} caught, {report['set_aside']} set aside, {len(report['undeclared'])} undeclared of {report['total']} mutants")
    for survivor in report["undeclared"]:
        print(f"  SURVIVED  {survivor['operator']}  {survivor['label']}")
    if report["adequate"]:
        print("js-mutate: every mutant is caught or declared equivalent — the suite is mutation-adequate.")
        return 0
    print("js-mutate: undeclared survivors above — add a test that catches each, or declare it equivalent in conformance/mutants_setaside.json.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(run(sys.argv[1]))
