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
    return [] if actual == expected else [f"HC008 callback anchors {actual!r}, expected {expected!r}"]
