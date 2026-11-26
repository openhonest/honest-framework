# scenario: _descend retains JavaScript scope nodes without visiting their bodies
# inherits: hd=python/honest-check/honest-check.hd::_descend -> feature=specs/features/honest-check.feature::_descend retains JavaScript scope nodes without visiting their bodies

from honest_check import build_context
from honest_check.nodes import _descend


def probe_descend_javascript_scopes():
    source = b"{ before(); function inner() { return document.cookie; } after(); }"
    root = build_context(source, "case.js", {})["root"]
    descendants = _descend(root.named_children[0])
    actual = [(node.type, node.text) for node in descendants]
    expected = [
        ("expression_statement", b"before();"),
        ("call_expression", b"before()"),
        ("identifier", b"before"),
        ("arguments", b"()"),
        ("function_declaration", b"function inner() { return document.cookie; }"),
        ("expression_statement", b"after();"),
        ("call_expression", b"after()"),
        ("identifier", b"after"),
        ("arguments", b"()"),
    ]
    failures = [] if actual == expected else [f"JavaScript scope descendants {actual!r}, expected {expected!r}"]
    scope_cases = (
        (b"const inner = function () { return document.cookie; };", "function_expression"),
        (b"function* inner() { yield document.cookie; }", "generator_function_declaration"),
        (b"const inner = function* () { yield document.cookie; };", "generator_function"),
        (b"const receiver = {inner() { return document.cookie; }};", "method_definition"),
    )
    for statement, kind in scope_cases:
        root = build_context(b"{ " + statement + b" }", "case.js", {})["root"]
        descendants = _descend(root.named_children[0])
        if root.has_error or not any(node.type == kind for node in descendants) or any(
            node.text == b"document.cookie" for node in descendants
        ):
            failures.append(f"{kind}: expected a retained scope boundary with no nested read")
    return failures
