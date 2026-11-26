# scenario: _hc_p004 uses the nearest owner and its own boundary evidence
# inherits: hd=python/honest-check/honest-check.hd::_hc_p004 -> feature=specs/features/honest-check.feature::_hc_p004 uses the nearest owner and its own boundary evidence


def probe_p004_hc_p004_nearest_owner():
    from honest_check import build_context
    from honest_check.rules import _hc_p004
    from honest_design import read_hd

    source = (
        b'// honest: boundary\n'
        b'function above() {\n'
        b'  fetch("/boundary");\n'
        b'  function nested() {\n'
        b'    fetch("/nested");\n'
        b'  }\n'
        b'}\n'
        b'function same() { // honest: boundary\n'
        b'  fetch("/same");\n'
        b'  function inside() {\n'
        b'    fetch("/unmarked");\n'
        b'  }\n'
        b'}\n'
        b'// honest: boundary\n'
        b'\n'
        b'function separated() {\n'
        b'  fetch("/separated");\n'
        b'}\n'
    )
    ctx = build_context(source, "case.js", {})
    assert not ctx["root"].has_error, ctx["root"]
    selected = [entry["source_location"] for entry in _hc_p004(ctx)]
    expected = ["case.js:5:5", "case.js:11:5", "case.js:17:3"]
    failures = [] if selected == expected else [f"nearest comment owner -> {selected!r}, expected {expected!r}"]
    role_sources = (
        ("case.js", b'function exempt() { fetch("/path"); }'),
        ("case.rb", b'def exempt\n File.read("path")\nend\n'),
        ("case.go", b'package example\nfunc exempt() { os.Open("path") }\n'),
    )
    for role in ("boundary_in", "boundary_out", "reader"):
        raw_hd = f"module example\n\n  {role} fn exempt : () -> any side_effect reads \"file\"\n"
        declaration = read_hd(raw_hd)["ok"]["modules"][0]
        for path, source in role_sources:
            ctx = build_context(source, path, {})
            assert not ctx["root"].has_error, ctx["root"]
            ctx["roles"] = {entry["name"]: entry["role"] for entry in declaration["functions"]}
            if findings := _hc_p004(ctx):
                failures.append(f"{path} {role} companion should exempt its matching function, got {findings!r}")
    go_source = (
        b'package example\n'
        b'func load() {\n'
        b'  os.Open("outer")\n'
        b'  func() { os.Open("anonymous") }()\n'
        b'}\n'
    )
    ctx = build_context(go_source, "case.go", {})
    assert not ctx["root"].has_error, ctx["root"]
    locations = [entry["source_location"] for entry in _hc_p004(ctx)]
    if locations != ["case.go:3:3"]:
        failures.append(f"Go function literal and its named outer function produced {locations!r}")
    return failures
