# scenario: check_per_file skips local feature rules when FEATURES is absent or unreadable
# inherits: hd=python/honest-check/honest-check.hd::check_per_file -> feature=specs/features/honest-check.feature::check_per_file skips local feature rules when FEATURES is absent or unreadable


def probe_check_per_file_unreadable_features():
    from honest_check import build_context, check_per_file

    failures = []
    for label, prefix in (("absent", b""), ("unreadable", b"FEATURES = load_flags()\n")):
        source = prefix + b'HANDLERS = {}\nresult = HANDLERS[feature_state(state, "missing")]\n'
        findings = [
            finding for finding in check_per_file(build_context(source, "case.py", {}))
            if finding["rule_id"] in {"HC-HF001", "HC-HF002"}
        ]
        if findings:
            failures.append(f"{label} FEATURES -> {findings!r}, expected no local feature finding")
    return failures
