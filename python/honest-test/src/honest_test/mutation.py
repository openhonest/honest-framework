"""Mutation adequacy (section 9.6): change the source in small mechanical ways, require the suite to fail.

Coverage (sections 9.1-9.4) shows a line ran; it cannot show the suite would catch that line being wrong.
Mutation adds that measure. Each operator is a pure tree-sitter transform that finds every site it
applies to and produces one mutated source per site — the way the generators enumerate a Set. The
changes are the fixed, finite section 9.6 list. The mutants are data; running each against a module's
conformance suite and accounting for caught-versus-set-aside is the gate layered above these transforms.

A mutant is `{operator, label, source}`: the operator that made it, a label naming the site and change,
and the full mutated source (a string, so the enumeration is a portable value). `enumerate_mutants`
parses the source once and runs every operator over it.
"""

from honest_parse import node_text, parse_python, walk

# Comparison swap (section 9.6): each operator token to its pair. Closed, finite — the swap is its own
# inverse, so applying the set twice is the identity.
_COMPARISON_SWAP = {"<": "<=", "<=": "<", ">": ">=", ">=": ">", "==": "!=", "!=": "=="}
_BOOLEAN_SWAP = {"and": "or", "or": "and"}
_BOOL_LITERAL_SWAP = {"True": "False", "False": "True"}
_MEMBERSHIP_SWAP = {"in": "not in", "not in": "in"}
_RESULT_SWAP = {"ok": "err", "err": "ok"}


def _edit(source: bytes, start: int, end: int, replacement: bytes) -> bytes:
    """The source with bytes [start, end) replaced by `replacement`. Pure."""
    return source[:start] + replacement + source[end:]


def _is_docstring(string_node) -> bool:
    """Whether a string node is a docstring — a bare string that is the first statement of its module or
    block. A docstring is ignored at runtime, so emptying or removing it is a universally equivalent
    mutant; the engine skips it rather than make every module declare it set-aside."""
    statement = string_node.parent
    if statement.type != "expression_statement":
        return False
    siblings = [child for child in statement.parent.named_children if child.type != "comment"]
    # tree-sitter returns a fresh node object from `.parent` vs `.named_children`, so compare by the
    # node's unique start byte rather than identity: the docstring is the first statement of its block.
    return siblings[0].start_byte == statement.start_byte


def _is_annotation_only(statement) -> bool:
    """Whether a statement is a bare type annotation (`name: type`, no value) — a field declaration with
    no runtime effect (a TypedDict field, an `__annotations__` entry), so removing it cannot change the
    result. A universally equivalent mutant, like a docstring; the engine skips it rather than make every
    module declare it set-aside. `name: type = value` has a value and is left removable."""
    if statement.type != "expression_statement":
        return False
    inner = statement.children[0]
    return inner.type == "assignment" and inner.child_by_field_name("type") is not None and inner.child_by_field_name("right") is None


def _comparison_swaps(tree, source: bytes) -> list:
    """Every comparison-swap mutant (section 9.6): each `<`, `<=`, `>`, `>=`, `==`, `!=` token swapped to
    its pair, one mutant per site. Pure."""
    mutants = []
    for node in walk(tree.root_node):
        if node.type != "comparison_operator":
            continue
        for child in node.children:
            text = node_text(child, source)
            if text not in _COMPARISON_SWAP:
                continue
            swapped = _COMPARISON_SWAP[text]
            mutated = _edit(source, child.start_byte, child.end_byte, swapped.encode("utf-8"))
            mutants.append({"operator": "comparison_swap", "label": f"{text}->{swapped}@{child.start_byte}", "source": mutated.decode("utf-8")})
    return mutants


def _mutant(operator, label, source_bytes, start, end, replacement):
    """One mutant record: the operator, a label naming the site and change, and the mutated source."""
    return {"operator": operator, "label": label, "source": _edit(source_bytes, start, end, replacement).decode("utf-8")}


def _number_shifts(tree, source: bytes) -> list:
    """Every number-shift mutant (section 9.6): each integer or float literal n replaced by n+1 and by
    n-1. Integer bases (hex/octal/binary) and digit separators are read with int(text, 0); a complex
    literal (text ending in j) has no single 'one' to add and is skipped rather than crashing. Pure."""
    mutants = []
    for node in walk(tree.root_node):
        if node.type not in ("integer", "float"):
            continue
        text = node_text(node, source)
        if text[-1] in ("j", "J"):
            continue  # a complex literal (1j) has no single 'one' to add — skip rather than crash.
        value = int(text, 0) if node.type == "integer" else float(text)
        for shift in (1, -1):
            mutants.append(_mutant("number_shift", f"{value}->{value + shift}@{node.start_byte}", source, node.start_byte, node.end_byte, str(value + shift).encode("utf-8")))
    return mutants


def _condition_node(node):
    """The boolean condition of a conditional construct, or None if `node` is not one. The branch
    statements (if/elif/while) carry it as a `condition` field; the ternary, the assert, and the
    comprehension filter name it positionally — the expression immediately after their keyword."""
    if node.type in ("if_statement", "elif_clause", "while_statement"):
        return node.child_by_field_name("condition")
    if node.type == "conditional_expression":
        return node.children[2]
    if node.type in ("assert_statement", "if_clause"):
        return node.children[1]
    return None


def _condition_flips(tree, source: bytes) -> list:
    """Every condition-flip mutant (section 9.6): `and`<->`or`, a `not` removed, and a condition negated
    (`c` -> `not (c)`) at every conditional construct — the `x` -> `not x` case. Pure."""
    mutants = []
    for node in walk(tree.root_node):
        if node.type == "boolean_operator":
            for child in node.children:
                if child.type in _BOOLEAN_SWAP:
                    swapped = _BOOLEAN_SWAP[child.type]
                    mutants.append(_mutant("condition_flip", f"{child.type}->{swapped}@{child.start_byte}", source, child.start_byte, child.end_byte, swapped.encode("utf-8")))
        elif node.type == "not_operator":
            operand = node.children[1]
            mutants.append(_mutant("condition_flip", f"drop-not@{node.start_byte}", source, node.start_byte, node.end_byte, node_text(operand, source).encode("utf-8")))
        else:
            condition = _condition_node(node)
            if condition is not None:
                negated = b"not (" + node_text(condition, source).encode("utf-8") + b")"
                mutants.append(_mutant("condition_flip", f"add-not@{condition.start_byte}", source, condition.start_byte, condition.end_byte, negated))
    return mutants


def _dict_key_swaps(tree, source: bytes) -> list:
    """Every dict-key-swap mutant (section 9.6): in a dictionary literal with two or more string keys,
    each key replaced by the next sibling key (cyclically), one mutant per key — so reading the wrong
    key, or a key gone missing, is caught. Non-string keys and splat entries are left alone. Pure."""
    mutants = []
    for node in walk(tree.root_node):
        if node.type != "dictionary":
            continue
        string_keys = []
        for child in node.named_children:
            key = child.child_by_field_name("key")
            if key is not None and key.type == "string":
                string_keys.append(key)
        if len(string_keys) < 2:
            continue
        for index, key in enumerate(string_keys):
            sibling = string_keys[(index + 1) % len(string_keys)]
            mutants.append(_mutant("key_swap", f"key->sibling@{key.start_byte}", source, key.start_byte, key.end_byte, node_text(sibling, source).encode("utf-8")))
    return mutants


def _constant_replaces(tree, source: bytes) -> list:
    """Every constant-replace mutant (section 9.6): `True`<->`False`, and a non-empty string literal made
    empty. (The 0->1 case is the number shift.) Pure."""
    mutants = []
    for node in walk(tree.root_node):
        if node.type in ("true", "false"):
            text = node_text(node, source)
            swapped = _BOOL_LITERAL_SWAP[text]
            mutants.append(_mutant("constant_replace", f"{text}->{swapped}@{node.start_byte}", source, node.start_byte, node.end_byte, swapped.encode("utf-8")))
        elif node.type == "string" and any(child.type == "string_content" for child in node.children) and not _is_docstring(node):
            mutants.append(_mutant("constant_replace", f"string->empty@{node.start_byte}", source, node.start_byte, node.end_byte, b'""'))
    return mutants


def _result_swaps(tree, source: bytes) -> list:
    """Every result-swap mutant (section 9.6): an `ok(...)` call's callee swapped to `err`, and vice
    versa. Pure."""
    mutants = []
    for node in walk(tree.root_node):
        if node.type != "call":
            continue
        callee = node.children[0]
        text = node_text(callee, source)
        if callee.type == "identifier" and text in _RESULT_SWAP:
            swapped = _RESULT_SWAP[text]
            mutants.append(_mutant("result_swap", f"{text}->{swapped}@{callee.start_byte}", source, callee.start_byte, callee.end_byte, swapped.encode("utf-8")))
    return mutants


def _membership_changes(tree, source: bytes) -> list:
    """Every membership-change mutant (section 9.6): `in`<->`not in`. Pure."""
    mutants = []
    for node in walk(tree.root_node):
        if node.type != "comparison_operator":
            continue
        for child in node.children:
            text = node_text(child, source)
            if text in _MEMBERSHIP_SWAP:
                swapped = _MEMBERSHIP_SWAP[text]
                mutants.append(_mutant("membership_change", f"{text}->{swapped}@{child.start_byte}", source, child.start_byte, child.end_byte, swapped.encode("utf-8")))
    return mutants


def _line_removals(tree, source: bytes) -> list:
    """Every line-removal mutant (section 9.6): in a container of two or more statements, one statement
    is deleted, leaving the rest. A block's sole statement cannot be deleted without breaking the block,
    so it is replaced by `pass` — its effect removed while the source still parses. A docstring, a bare
    annotation, or a statement already `pass` is universally equivalent and skipped; a module's sole
    statement is left to deletion (a module carries many top-level statements). Pure."""
    mutants = []
    for node in walk(tree.root_node):
        if node.type not in ("block", "module"):
            continue
        statements = [child for child in node.named_children if child.type != "comment"]
        for statement in statements:
            string_child = next((child for child in statement.named_children if child.type == "string"), None)
            if (string_child is not None and _is_docstring(string_child)) or _is_annotation_only(statement):
                continue
            if len(statements) >= 2:
                mutants.append(_mutant("line_removal", f"remove@{statement.start_byte}", source, statement.start_byte, statement.end_byte, b""))
            elif node.type == "block" and node_text(statement, source) != "pass":
                mutants.append(_mutant("line_removal", f"sole-pass@{statement.start_byte}", source, statement.start_byte, statement.end_byte, b"pass"))
    return mutants


def _branch_arm_removals(tree, source: bytes) -> list:
    """Every branch-arm-removal mutant (section 9.6): an `elif` or `else` clause of an `if` deleted
    whole, so its arm never runs. The leading `if` arm cannot be dropped without restructuring and is
    left to the other operators; only the trailing optional arms are removed. Pure."""
    mutants = []
    for node in walk(tree.root_node):
        if node.type != "if_statement":
            continue
        for child in node.children:
            if child.type in ("elif_clause", "else_clause"):
                mutants.append(_mutant("line_removal", f"drop-arm@{child.start_byte}", source, child.start_byte, child.end_byte, b""))
    return mutants


_OPERATORS = (_comparison_swaps, _number_shifts, _condition_flips, _constant_replaces, _result_swaps, _membership_changes, _dict_key_swaps, _line_removals, _branch_arm_removals)


def enumerate_mutants(source: str) -> list:
    """Every mutant of `source` (section 9.6): run each operator over the parsed source and collect one
    mutant per site, the full mutant list the runner checks the suite against. Pure."""
    source_bytes = source.encode("utf-8")
    tree = parse_python(source_bytes)
    mutants = []
    for operator in _OPERATORS:
        mutants.extend(operator(tree, source_bytes))
    return mutants


def run_mutants(mutants, run_suite) -> list:
    """The mutants a suite does not catch (section 9.6). `run_suite(mutated_source) -> bool` returns
    whether the conformance suite still PASSES on the mutated source; a mutant that leaves the suite
    passing was not caught, so it survives. Returns the survivors. The decision is pure — running the
    suite is the injected I/O seam, so this is testable without subprocesses."""
    return [mutant for mutant in mutants if run_suite(mutant["source"])]


def mutation_adequacy(mutants, survivors, set_aside) -> dict:
    """The adequacy report for a module (section 9.6): caught + set_aside == total. A survivor whose label
    appears in `set_aside` (a `{label: reason}` map of mutants that cannot change the result) is declared
    equivalent; any other survivor is undeclared and fails the gate. Pure. Returns the totals and the
    undeclared survivors, with `adequate` true only when none are undeclared."""
    undeclared = [{"operator": mutant["operator"], "label": mutant["label"]} for mutant in survivors if mutant["label"] not in set_aside]
    return {
        "total": len(mutants),
        "caught": len(mutants) - len(survivors),
        "set_aside": len(survivors) - len(undeclared),
        "undeclared": undeclared,
        "adequate": not undeclared,
    }
