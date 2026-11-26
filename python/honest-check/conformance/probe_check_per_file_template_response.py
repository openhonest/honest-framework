# scenario: check_per_file identifies a declared template response without an emits vocabulary
# inherits: hd=python/honest-check/honest-check.hd::check_per_file -> feature=specs/features/honest-check.feature::check_per_file identifies a declared template response without an emits vocabulary

from honest_check import build_context, check_per_file


def probe_check_per_file_template_response():
    source = b"def render() -> TemplateResponse:\n    return make_page()\n"
    ctx = build_context(source, "case.py", {})
    observed = [
        (finding["severity"], finding["source_location"])
        for finding in check_per_file(ctx)
        if finding["rule_id"] == "HC-P017"
    ]
    expected = [("error", "case.py:1:1")]
    return [] if observed == expected else [f"expected located TemplateResponse error {expected!r}, got {observed!r}"]
