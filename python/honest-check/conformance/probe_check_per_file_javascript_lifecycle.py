# scenario: check_per_file reports qualified JavaScript lifecycle calls
# inherits: hd=python/honest-check/honest-check.hd::check_per_file -> feature=specs/features/honest-check.feature::check_per_file reports qualified JavaScript lifecycle calls

from honest_check import build_context, check_per_file


def probe_check_per_file_javascript_lifecycle():
    source = b"view.componentDidMount();\n  componentDidMount();\nview.render();\n"
    ctx = build_context(source, "case.js", {})
    findings = [item for item in check_per_file(ctx) if item["rule_id"] == "HC-P011"]
    actual = sorted(
        (
            item["severity"],
            item["source_location"],
            "componentDidMount" in item["message"],
            "htmx attributes" in item["message"].casefold()
            or "server-rendered html" in item["message"].casefold(),
        )
        for item in findings
    )
    expected = [
        ("error", "case.js:1:1", True, True),
        ("error", "case.js:2:3", True, True),
    ]
    if actual != expected:
        return [f"expected two located lifecycle errors naming the hook and its alternatives, got {findings!r}"]
    failures = []
    for path, names in (
        ("extended.js", ("componentWillUnmount", "componentDidUpdate")),
        ("extended.ts", ("ngOnInit", "ngOnDestroy")),
    ):
        source = "".join(f"view.{hook}();\n" for hook in names).encode()
        findings = [
            item for item in check_per_file(build_context(source, path, {}))
            if item["rule_id"] == "HC-P011"
        ]
        expected = [
            ("error", f"{path}:{line}:1", hook) for line, hook in enumerate(names, 1)
        ]
        actual = [
            (item["severity"], item["source_location"], next(
                (hook for hook in names if hook in item["message"]), None
            ))
            for item in findings
        ]
        remedies = all(
            "htmx attributes" in item["message"].casefold()
            or "server-rendered html" in item["message"].casefold()
            for item in findings
        )
        if actual != expected or not remedies:
            failures.append(f"{path}: expected lifecycle errors {expected!r} with their remedies, got {findings!r}")
    return failures
