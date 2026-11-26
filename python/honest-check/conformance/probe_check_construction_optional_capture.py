# scenario: check_construction checks optional capture base names with HC006
# inherits: hd=python/honest-check/honest-check.hd::check_construction -> feature=specs/features/honest-check.feature::check_construction checks optional capture base names with HC006


def probe_check_construction_optional_capture():
    from honest_check import build_context, check_construction

    cases = (
        ("Part", []),
        ("Other", [("error", "case.py:3:14", True, True), ("error", "case.py:4:14", True, True)]),
    )
    failures = []
    for base, expected in cases:
        source = (
            "from honest_type import composed, maybe, vocabulary\n"
            f'cards = vocabulary({{{base!r}: {{"value"}}}}, [\n'
            '    composed("First", requires={}, captures=maybe("Part")),\n'
            '    composed("Second", requires={}, captures=maybe("Part")),\n'
            '])\n'
        ).encode()
        findings = [
            finding for finding in check_construction(build_context(source, "case.py", {}))
            if finding["rule_id"] == "HC006"
        ]
        actual = sorted(
            (
                finding["severity"], finding["source_location"],
                "Part" in finding["message"], "captur" in finding["message"].casefold(),
            )
            for finding in findings
        )
        if actual != expected:
            failures.append(f"base {base!r}: expected HC006 outcomes {expected!r}, got {findings!r}")
    return failures
