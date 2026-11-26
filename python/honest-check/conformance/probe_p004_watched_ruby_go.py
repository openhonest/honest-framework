# scenario: watched matches static Ruby methods and Go selectors
# inherits: hd=python/honest-check/honest-check.hd::watched -> feature=specs/features/honest-check.feature::watched matches static Ruby methods and Go selectors


def probe_p004_watched_ruby_go():
    from honest_check import build_context, watched

    cases = (
        ("case.rb", "File.read('path')", "call", "File.read", "IO.read"),
        ("case.rb", "IO.read('path')", "call", "IO.read", "File.read"),
        ("case.rb", "file.read('path')", "call", "file.read", "File.read"),
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
    computed = (
        ("case.rb", "file_factory().read('path')", "call", "file_factory().read"),
        ("case.go", 'package example\nvar _ = get().Open("path")', "selector_expression", "get().Open"),
        ("case.go", 'package example\nvar _ = store.file.Open("path")', "selector_expression", "store.file.Open"),
    )
    for path, source, kind, spelling in computed:
        ctx = build_context(source.encode(), path, {})
        assert not ctx["root"].has_error, ctx["root"]
        target = next(node for node in ctx["nodes"] if node.type == kind)
        if watched(target, {spelling}):
            failures.append(f"computed target {spelling!r} supplied a static watch name")
    return failures
