"""JavaScript structural rules (spec section 5).

The Honest Code principles are language-agnostic; honest-check enforces them over each target
language's tree-sitter grammar. This module implements their JavaScript form over
tree-sitter-javascript nodes. The first rule is HC-P003 (class declaration): a JavaScript class is
honest only as a subclass of Error (a thrown fault), the same exemption Python gives Exception
subclasses. Every other class — bare or extending anything else — smuggles state and behaviour into
an object and is rejected.

Pure: each rule is `check(root_node, source_bytes, path) -> list[Diagnostic]`, the same contract as
the Python rules in rules.py. The honest-type-specific rules (vocabularies, chains, links) do not
apply to vanilla JavaScript and are not implemented here.
"""

from honest_check.diagnostics import Diagnostic, diagnostic
from honest_parse import line_col, node_text, walk

# Section 5.3 — the only base a JavaScript class may extend (a thrown fault). Everything else,
# including a bare class implicitly extending Object, is inheritance and is rejected.
_ALLOWED_JS_CLASS_BASES = frozenset({"Error"})

# Section 5.7 — framework lifecycle hooks. Their presence wires behaviour to a hidden lifecycle
# instead of to server-rendered HTML / HTMX attributes (honest-DOM anti-patterns, honest-DOM §6).
_JS_LIFECYCLE_HOOKS = frozenset(
    {
        "useEffect",
        "useLayoutEffect",
        "componentDidMount",
        "componentDidUpdate",
        "componentWillUnmount",
        "ngOnInit",
        "ngOnDestroy",
        "addEventListener",
        "removeEventListener",
    }
)


def _is_class_node(node) -> bool:
    """Whether a node is a JavaScript class definition: a named `class_declaration`, or an anonymous
    `class` expression (distinguished from the `class` keyword token by carrying a body)."""
    if node.type == "class_declaration":
        return True
    return node.type == "class" and node.child_by_field_name("body") is not None


def _class_name(node, source: bytes) -> str:
    """The declared name of a JavaScript class, or '<anonymous>' for a class expression."""
    name = node.child_by_field_name("name")
    return node_text(name, source) if name is not None else "<anonymous>"


def _class_base(node, source: bytes):
    """The superclass name of a JavaScript class (the expression after `extends`), or None when the
    class declares no heritage."""
    for child in node.children:
        if child.type == "class_heritage":
            named = child.named_children
            return node_text(named[0], source) if named else None
    return None


def check_hc_p003_js(root, source: bytes, path: str) -> list[Diagnostic]:
    """HC-P003 (JavaScript) — a class is honest only as a subclass of Error (section 5.3). A bare class
    or one extending anything else is inheritance: use a plain object for data or a pure function."""
    out: list[Diagnostic] = []
    for node in walk(root):
        if not _is_class_node(node):
            continue
        name = _class_name(node, source)
        base = _class_base(node, source)
        line, col = line_col(node)
        if base is None:
            out.append(
                diagnostic(
                    "HC-P003",
                    "error",
                    path,
                    line,
                    col,
                    f"Class '{name}' has no declared base. Honest Code permits a JavaScript class only "
                    "as a subclass of Error. Use a plain object for data or a pure function.",
                )
            )
        elif base not in _ALLOWED_JS_CLASS_BASES:
            out.append(
                diagnostic(
                    "HC-P003",
                    "error",
                    path,
                    line,
                    col,
                    f"Class '{name}' inherits from '{base}'. Use composition over inheritance.",
                )
            )
    return out


def _js_call_name(call_node, source: bytes) -> str:
    """The callee name of a JavaScript call: 'foo' for foo(), 'bar' for obj.bar()."""
    fn = call_node.child_by_field_name("function")
    if fn is None:
        return ""
    if fn.type == "member_expression":
        return node_text(fn.child_by_field_name("property"), source)
    return node_text(fn, source)


def check_hc_p011_js(root, source: bytes, path: str) -> list[Diagnostic]:
    """HC-P011 (JavaScript) — a framework lifecycle hook (section 5.7). useEffect, addEventListener and
    their kin wire behaviour to a hidden lifecycle; use HTMX attributes or server-rendered HTML."""
    out: list[Diagnostic] = []
    for node in walk(root):
        if node.type != "call_expression":
            continue
        name = _js_call_name(node, source)
        if name not in _JS_LIFECYCLE_HOOKS:
            continue
        line, col = line_col(node)
        out.append(
            diagnostic(
                "HC-P011",
                "error",
                path,
                line,
                col,
                f"Lifecycle hook '{name}'. Use HTMX attributes or server-rendered HTML.",
            )
        )
    return out
