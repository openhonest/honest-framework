# scenario: module_dict_literals distinguishes an empty FEATURES literal from an unreadable binding
# inherits: hd=python/honest-check/honest-check.hd::module_dict_literals -> feature=specs/features/honest-check.feature::module_dict_literals distinguishes an empty FEATURES literal from an unreadable binding


def probe_module_dict_literals_empty_features():
    from honest_check import build_context, module_dict_literals

    cases = (
        ("literal", b"FEATURES = {}", {"FEATURES": set()}),
        ("absent", b"config = 1", {}),
        ("unreadable", b"FEATURES = load_flags()", {}),
    )
    failures = []
    for label, source, expected in cases:
        result = module_dict_literals(build_context(source, "case.py", {}))
        if result != expected:
            failures.append(f"{label} FEATURES -> {result!r}, expected {expected!r}")
    return failures
