# scenario: check_per_file reports an unknown literal flag against an explicitly empty FEATURES vocabulary
# inherits: hd=python/honest-check/honest-check.hd::check_per_file -> feature=specs/features/honest-check.feature::check_per_file reports an unknown literal flag against an explicitly empty FEATURES vocabulary


def probe_check_per_file_empty_features():
    from honest_check import build_context, check_per_file

    source = b"""FEATURES = {}
first = feature_state(state, "missing")
second = feature_state(state, dynamic_flag)
"""
    findings = [
        finding for finding in check_per_file(build_context(source, "case.py", {}))
        if finding["rule_id"] == "HC-HF001"
    ]
    observed = [(entry["severity"], entry["source_location"], "missing" in entry["message"]) for entry in findings]
    expected = [("error", "case.py:2:9", True)]
    return [] if observed == expected else [f"explicit empty FEATURES literal and dynamic calls -> {observed!r}, expected {expected!r}"]
