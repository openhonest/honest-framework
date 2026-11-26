# scenario: _hc_p004 reports watched operations in named non-boundary host functions
# inherits: hd=python/honest-check/honest-check.hd::_hc_p004 -> feature=specs/features/honest-check.feature::_hc_p004 reports watched operations in named non-boundary host functions


def probe_p004_hc_p004_host_functions():
    from honest_check import build_context
    from honest_check.rules import _hc_p004

    cases = (
        ("case.js", (
            b'fetch("/outside");',
            b'function load() {',
            b'  fetch("/inside");',
            b'  localStorage.getItem("key");',
            b'  sessionStorage.setItem("key", "value");',
            b'  new XMLHttpRequest();',
            b'  ordinary();',
            b'}',
        ), ((3, 3), (4, 3), (5, 3), (6, 3))),
        ("case.rb", (
            b'File.read("outside")',
            b'def load',
            b'  File.read("inside")',
            b'  ordinary()',
            b'end',
            b'def self.read',
            b'  IO.read("inside")',
            b'end',
        ), ((3, 3), (7, 3))),
        ("case.go", (
            b'package example',
            b'var _, _ = os.Open("outside")',
            b'func load() {',
            b'  os.Open("inside")',
            b'  ordinary()',
            b'}',
            b'func (r Reader) Read() {',
            b'  ioutil.ReadFile("inside")',
            b'}',
        ), ((4, 3), (8, 3))),
    )
    failures = []
    for path, lines, locations in cases:
        ctx = build_context(b"\n".join(lines) + b"\n", path, {})
        assert not ctx["root"].has_error, ctx["root"]
        actual = [(finding["rule_id"], finding["severity"], finding["source_location"]) for finding in _hc_p004(ctx)]
        expected = [("HC-P004", "error", f"{path}:{line}:{column}") for line, column in locations]
        if actual != expected:
            failures.append(f"{path} named I/O findings -> {actual!r}, expected {expected!r}")
    return failures
