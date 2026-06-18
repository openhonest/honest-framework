"""Rule registry and the check_source entry point (sections 4, 8).

Each rule is a pure function `check(root_node, source_bytes, path) -> list[Diagnostic]`.
Rules are registered in `_ALL_CHECKS`; `check_source` parses once, short-circuits on
a syntax error (HC-SYN), then runs every registered rule. New rules are added by
writing the function and appending it to the registry — a row, not a branch.

This unit implements the two structural rules that make class-based smuggling and
value-dispatch chains impossible to represent: HC-P003 (class declaration) and
HC-P001 (if/elif/else dispatch). Both cite honest-check-architecture.md section 4.2.
"""

from honest_check.diagnostics import Diagnostic, diagnostic
from honest_check.parse import first_error_node, line_col, node_text, parse_python, walk

# Section 4.2 / 5.3 — the only class bases Honest Code permits.
_ALLOWED_CLASS_BASES = frozenset(
    {"TypedDict", "Protocol", "ABC", "Exception", "BaseException", "Error"}
)

# Minimum branch count for HC-P001 to consider an if-chain a dispatch (section 4.2).
_DISPATCH_BRANCH_THRESHOLD = 3


def check_hc_syn(root, source: bytes, path: str) -> list[Diagnostic]:
    """HC-SYN — source does not parse. Short-circuits all other rules."""
    if not root.has_error:
        return []
    node = first_error_node(root)
    line, col = line_col(node) if node is not None else (1, 1)
    return [
        diagnostic("HC-SYN", "error", path, line, col, "Source does not parse.")
    ]


def _simple_base_name(text: str) -> str:
    """Reduce a base expression to its bare name: 'typing.Protocol' -> 'Protocol'."""
    return text.split("[")[0].split(".")[-1].strip()


def _class_base_names(class_node, source: bytes) -> list[str]:
    """Names of a class's explicit bases, ignoring keyword args like total=False."""
    supers = class_node.child_by_field_name("superclasses")
    if supers is None:
        return []
    names = []
    for child in supers.named_children:
        if child.type == "subscript":
            value = child.child_by_field_name("value")
            names.append(node_text(value, source) if value is not None else "")
        if child.type in ("identifier", "attribute"):
            names.append(node_text(child, source))
    return names


def check_hc_p003(root, source: bytes, path: str) -> list[Diagnostic]:
    """HC-P003 — class declaration (bare class, or inheritance from a non-approved base)."""
    out: list[Diagnostic] = []
    for node in walk(root):
        if node.type != "class_definition":
            continue
        name_node = node.child_by_field_name("name")
        name = node_text(name_node, source) if name_node is not None else "<anonymous>"
        line, col = line_col(node)
        bases = _class_base_names(node, source)
        if not bases:
            out.append(
                diagnostic(
                    "HC-P003",
                    "error",
                    path,
                    line,
                    col,
                    f"Class '{name}' has no declared base. Honest Code permits class "
                    "definitions only as subclasses of TypedDict, Protocol, ABC, or a "
                    "declared Exception. Use a TypedDict for data shapes or a pure function.",
                )
            )
            continue
        for base in bases:
            if _simple_base_name(base) not in _ALLOWED_CLASS_BASES:
                out.append(
                    diagnostic(
                        "HC-P003",
                        "error",
                        path,
                        line,
                        col,
                        f"Class '{name}' inherits from '{base}'. "
                        "Use composition over inheritance.",
                    )
                )
    return out


def _equality_target(condition, source: bytes) -> str | None:
    """If `condition` is `IDENT == value`, return IDENT's text; else None."""
    if condition.type != "comparison_operator":
        return None
    if not any(child.type == "==" for child in condition.children):
        return None
    operands = condition.named_children
    if len(operands) < 2:
        return None
    left = operands[0]
    if left.type != "identifier":
        return None
    return node_text(left, source)


def _if_chain_conditions(if_node):
    """Every condition guarding a branch of an if-statement: the if plus each elif."""
    conditions = [if_node.child_by_field_name("condition")]
    for child in if_node.children:
        if child.type == "elif_clause":
            conditions.append(child.child_by_field_name("condition"))
    return [c for c in conditions if c is not None]


def check_hc_p001(root, source: bytes, path: str) -> list[Diagnostic]:
    """HC-P001 — if/elif/else chain dispatching on a single value. Use a dict table."""
    out: list[Diagnostic] = []
    for node in walk(root):
        if node.type != "if_statement":
            continue
        targets = [
            t
            for t in (_equality_target(c, source) for c in _if_chain_conditions(node))
            if t is not None
        ]
        if len(targets) < _DISPATCH_BRANCH_THRESHOLD:
            continue
        if len(set(targets)) != 1:
            continue
        line, col = line_col(node)
        out.append(
            diagnostic(
                "HC-P001",
                "error",
                path,
                line,
                col,
                "if/elif/else chain dispatches on value — use dict lookup. "
                "See honest-code-principles.md §3.",
            )
        )
    return out


# Registry. Order is report order; each entry is one rule function (section 8).
_ALL_CHECKS = (
    check_hc_p001,
    check_hc_p003,
)


def check_source(source: str, path: str) -> list[Diagnostic]:
    """Parse `source`, then run every registered rule. The entry point (section 1)."""
    src_bytes = source.encode("utf-8")
    root = parse_python(src_bytes).root_node
    syntax = check_hc_syn(root, src_bytes, path)
    if syntax:
        return syntax
    out: list[Diagnostic] = []
    for check in _ALL_CHECKS:
        out.extend(check(root, src_bytes, path))
    return out
