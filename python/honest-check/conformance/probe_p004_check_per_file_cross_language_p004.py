# scenario: check_per_file reports HC-P004 for named JavaScript Ruby and Go functions
# inherits: hd=python/honest-check/honest-check.hd::check_per_file -> feature=specs/features/honest-check.feature::check_per_file reports HC-P004 for named JavaScript Ruby and Go functions


def probe_p004_check_per_file_cross_language_p004():
    from honest_check import build_context, check_per_file
    from honest_design import read_hd

    parsed = read_hd('module example\n\n  boundary_in fn exempt : () -> any side_effect reads "file"\n')["ok"]["modules"][0]
    roles = {entry["name"]: entry["role"] for entry in parsed["functions"]}
    cases = (
        ("case.js", b'function ordinary() {\n  fetch("/path");\n}\nfunction exempt() {\n  fetch("/path");\n}\n', 2),
        ("case.rb", b'def ordinary\n  File.read("path")\nend\ndef exempt\n  File.read("path")\nend\n', 2),
        ("case.go", b'package example\nfunc ordinary() {\n  os.Open("path")\n}\nfunc exempt() {\n  os.Open("path")\n}\n', 3),
    )
    failures = []
    for path, source, line in cases:
        ctx = build_context(source, path, {})
        assert not ctx["root"].has_error, ctx["root"]
        ctx["roles"] = roles
        actual = [(finding["severity"], finding["source_location"]) for finding in check_per_file(ctx)
                  if finding["rule_id"] == "HC-P004"]
        expected = [("error", f"{path}:{line}:3")]
        if actual != expected:
            failures.append(f"{path} public HC-P004 findings -> {actual!r}, expected {expected!r}")
    return failures
