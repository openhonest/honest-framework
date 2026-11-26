# scenario: watched matches static Ruby methods and Go selectors
# inherits: hd=python/honest-check/honest-check.hd::watched -> feature=specs/features/honest-check.feature::watched matches static Ruby methods and Go selectors


def probe_p004_watched_ruby_go():
    from honest_check import build_context, watched

    cases = (
        ("case.rb", "File.read('path')", "call", "File.read", "IO.read"),
        ("case.rb", "IO.read('path')", "call", "IO.read", "File.read"),
        ("case.rb", "Storage::File.read('path')", "call", "Storage::File.read", "Storage.File.read"),
        ("case.go", 'os.Open("path")', "selector_expression", "os.Open", "other.Open"),
        ("case.go", 'ioutil.ReadFile("path")', "selector_expression", "ioutil.ReadFile", "other.ReadFile"),
    )
    failures = []
    for path, expression, kind, expected, other in cases:
        source = expression if path.endswith("rb") else "package example\nvar _, _ = " + expression
        ctx = build_context(source.encode(), path, {})
        assert not ctx["root"].has_error, ctx["root"]
        target = next(node for node in ctx["nodes"] if node.type == kind)
        actual = (watched(target, {expected}), watched(target, {other}))
        if actual != (True, False):
            failures.append(f"{expected} static spelling -> {actual!r}, expected (True, False)")
    return failures
