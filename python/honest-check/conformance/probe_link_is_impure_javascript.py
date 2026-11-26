# scenario: link_is_impure detects watched JavaScript calls and value reads
# inherits: hd=python/honest-check/honest-check.hd::link_is_impure -> feature=specs/features/honest-check.feature::link_is_impure detects watched JavaScript calls and value reads

from honest_check import build_context, link_is_impure


def probe_link_is_impure_javascript():
    cases = (
        (b"() => Math.random()", True),
        (b"() => process.env", True),
        (b"() => process.argv", True),
        (b"() => process.pid", True),
        (b"() => process.platform", True),
        (b"() => process.version", True),
        (b"function () { return document.cookie; }", True),
        (b'() => { document.cookie = "x=1"; }', False),
        (b"() => { for (document.cookie of values) {} }", False),
        (b"() => { for (document.cookie in values) {} }", False),
        (b"() => { delete document.cookie; }", False),
        (b"() => { typeof document.cookie; }", True),
        (b"() => { [document.cookie] = values; }", False),
        (b"() => { ({key: document.cookie} = values); }", False),
        (b"() => { [...document.cookie] = values; }", False),
        (b"() => other.env", False),
        (b'() => "process.env"', False),
        (b"() => { const later = () => process.env; return 1; }", False),
    )
    watch = {
        "Math.random", "process.env", "process.argv", "process.pid",
        "process.platform", "process.version", "document.cookie",
    }
    failures = []
    for callback, expected in cases:
        ctx = build_context(b"const selected = link({}, " + callback + b");", "case.js", {})
        fdef = next(node for node in ctx["nodes"] if node.type in {"arrow_function", "function_expression"})
        actual = link_is_impure(ctx, fdef, watch, set())
        if actual is not expected:
            failures.append(f"{callback!r}: impurity {actual!r}, expected {expected!r}")
    return failures
