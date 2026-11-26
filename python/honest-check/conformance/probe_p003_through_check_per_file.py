# scenario: check_per_file reports a disallowed Python base alongside an approved base
# inherits: hd=python/honest-check/honest-check.hd::check_per_file -> feature=specs/features/honest-check.feature::check_per_file reports a disallowed Python base alongside an approved base


def probe_p003_through_check_per_file():
    import re
    from honest_check import build_context, check_per_file

    source = b"class Mixed(Protocol, Enum, metaclass=ABCMeta): pass\n"
    findings = check_per_file(build_context(source, "case.py", {}))
    actual = [
        (finding["severity"], finding["source_location"], bool(re.search(r"\bEnum\b", finding["message"])))
        for finding in findings if finding["rule_id"] == "HC-P003"
    ]
    expected = [("error", "case.py:1:1", True)]
    return [] if actual == expected else [f"HC-P003 per-file path -> {actual!r}, expected {expected!r}"]
