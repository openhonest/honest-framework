# scenario: own_body includes expression roots and excludes nested JavaScript bodies
# inherits: hd=python/honest-check/honest-check.hd::own_body -> feature=specs/features/honest-check.feature::own_body includes expression roots and excludes nested JavaScript bodies

from honest_check import build_context, own_body


def probe_own_body_javascript():
    source = b"""const arrow = () => Math.random();
const block = function () {
  function inner() { return document.cookie; }
  return process.env;
};
"""
    nodes = build_context(source, "case.js", {})["nodes"]
    arrow = next(node for node in nodes if node.type == "arrow_function")
    block = next(node for node in nodes if node.type == "function_expression")
    actual = (
        [node.text for node in own_body(arrow) if node.type == "call_expression"],
        [node.text for node in own_body(block) if node.type in {"return_statement", "member_expression", "statement_block"}],
    )
    expected = ([b"Math.random()"], [b"return process.env;", b"process.env"])
    failures = [] if actual == expected else [f"own-body call/return/read nodes {actual!r}, expected {expected!r}"]
    nested = build_context(b"const arrow = () => () => document.cookie;", "case.js", {})
    outer = next(node for node in nested["nodes"] if node.type == "arrow_function")
    nested_body = own_body(outer)
    if any(node.text == b"document.cookie" for node in nested_body):
        failures.append("own_body descended into the arrow expression's nested callback")
    return failures
