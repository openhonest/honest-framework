# scenario: called_name returns the final name of a qualified JavaScript call
# inherits: hd=python/honest-check/honest-check.hd::called_name -> feature=specs/features/honest-check.feature::called_name returns the final name of a qualified JavaScript call

from honest_check import build_context, called_name


def probe_called_name_javascript_qualified():
    ctx = build_context(b"view.componentDidMount();\n", "case.js", {})
    call = next(node for node in ctx["nodes"] if node.type == "call_expression")
    actual = called_name(ctx, call)
    expected = "componentDidMount"
    if actual != expected:
        return [f"called_name on view.componentDidMount() returned {actual!r}, expected {expected!r}"]
    return []
