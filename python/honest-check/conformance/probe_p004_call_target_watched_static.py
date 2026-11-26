# scenario: _call_target_watched matches only supported static operation heads
# inherits: hd=python/honest-check/honest-check.hd::_call_target_watched -> feature=specs/features/honest-check.feature::_call_target_watched matches only supported static operation heads


def probe_p004_call_target_watched_static():
    from honest_check import build_context
    from honest_check.rules import _call_target_watched

    cases = (
        ("case.py", 'os.open("path", 0)', "call", "os.open", True),
        ("case.js", 'fetch("/path")', "call_expression", "fetch", True),
        ("case.js", "new XMLHttpRequest()", "new_expression", "XMLHttpRequest", True),
        ("case.js", "new WebSocket()", "new_expression", "XMLHttpRequest", False),
        ("case.js", 'localStorage["getItem"]("k")', "call_expression", "localStorage.getItem", False),
        ("case.js", 'getStorage().getItem("k")', "call_expression", "localStorage.getItem", False),
        ("case.rb", "File.read('path')", "call", "File.read", True),
        ("case.rb", "IO.read('path')", "call", "IO.read", True),
        ("case.rb", "Other.read('path')", "call", "IO.read", False),
        ("case.go", 'os.Open("path")', "call_expression", "os.Open", True),
        ("case.go", 'ioutil.ReadFile("path")', "call_expression", "ioutil.ReadFile", True),
        ("case.go", 'other.Open("path")', "call_expression", "os.Open", False),
    )
    failures = []
    for path, expression, kind, name, expected in cases:
        source = expression if not path.endswith("go") else "package example\nvar _, _ = " + expression
        ctx = build_context(source.encode(), path, {})
        assert not ctx["root"].has_error, ctx["root"]
        operation = next(node for node in ctx["nodes"] if node.type == kind)
        actual = _call_target_watched(ctx, operation, {name})
        if actual is not expected:
            failures.append(f"{expression} versus {name}: matched {actual!r}, expected {expected!r}")
    return failures
