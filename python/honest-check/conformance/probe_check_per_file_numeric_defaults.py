# scenario: check_per_file reports only real-valued Python numeric defaults
# inherits: hd=python/honest-check/honest-check.hd::check_per_file -> feature=specs/features/honest-check.feature::check_per_file reports only real-valued Python numeric defaults

def probe_check_per_file_numeric_defaults():
    from honest_check import build_context, check_per_file

    source = (
        b"def check(\n"
        b"    hex_zero=0x0,\n"
        b"    oct_zero=0O_0,\n"
        b"    bin_zero=0B_0,\n"
        b"    dec_zero=0_0,\n"
        b"    float_zero=0.0,\n"
        b"    exponent_zero=0e3,\n"
        b"    imaginary_zero=0j,\n"
        b"    negative_zero=(-0),\n"
        b"    positive_zero=(+0.0),\n"
        b"    hex_nonzero=0x2,\n"
        b"    negative_float=-1.5,\n"
        b"    imaginary_nonzero=1j,\n"
        b"):\n    pass\n"
    )
    ctx = build_context(source, "case.py", {})
    try:
        result = check_per_file(ctx)
    except (ValueError, TypeError) as error:
        return [f"numeric defaults: raised {type(error).__name__}: {error}"]
    observed = [
        (finding["severity"], finding["source_location"])
        for finding in result if finding["rule_id"] == "HC-P015"
    ]
    expected = [("error", f"case.py:{line}:5") for line in (11, 12, 13)]
    return [] if observed == expected else [f"numeric diagnostics: returned {observed!r}, expected {expected!r}"]
