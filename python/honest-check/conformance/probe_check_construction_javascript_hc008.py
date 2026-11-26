# scenario: check_construction anchors JavaScript HC008 warnings to inline callbacks
# inherits: hd=python/honest-check/honest-check.hd::check_construction -> feature=specs/features/honest-check.feature::check_construction anchors JavaScript HC008 warnings to inline callbacks

from honest_check import build_context, check_construction


def probe_check_construction_javascript_hc008():
    source = b"""const call = link({}, () => Math.random());
const value = link({}, function () { return process.env; });
const door = link({boundary: true}, () => Math.random());
const nested = link({}, () => { const later = () => process.env; return 1; });
const clean = link({}, () => 42);
"""
    ctx = build_context(source, "case.js", {})
    findings = [finding for finding in check_construction(ctx) if finding["rule_id"] == "HC008"]
    actual = sorted((finding["severity"], finding["source_location"]) for finding in findings)
    expected = [("warning", "case.js:1:23"), ("warning", "case.js:2:24")]
    failures = [] if actual == expected else [f"HC008 callback anchors {actual!r}, expected {expected!r}"]
    for value in ("process.pid", "process.argv", "process.platform", "process.version", "document.cookie"):
        source = f"const value = link({{}}, () => {value});\n".encode()
        ctx = build_context(source, "case.js", {})
        findings = [item for item in check_construction(ctx) if item["rule_id"] == "HC008"]
        actual = [(item["severity"], item["source_location"]) for item in findings]
        expected = [("warning", "case.js:1:24")]
        if actual != expected:
            failures.append(f"{value}: expected {expected!r}, got {actual!r}")
    return failures
