# scenario: declared_seams
# inherits: hd=python/honest-check/honest-check.hd::declared_seams -> feature=specs/features/honest-check.feature::declared_seams


def probe_parsed_seams_declared_seams():
    from honest_check import declared_seams
    from honest_design import read_hd

    mixed = (
        'module sample\n\n'
        '  fn save : () -> any side_effect writes "" side_effect writes "DOM" side_effect writes "honest-persist"\n'
        '  fn load : () -> any side_effect reads "env:POOL_SIZE" side_effect reads "honest-parse.parse_source"\n'
    )
    only_world = 'module sample\n\n  fn save : () -> any side_effect writes "" side_effect writes "DOM"\n'
    expected_mixed = [
        {"caller": "save", "module": "honest-persist", "door": "", "direction": "writes"},
        {"caller": "load", "module": "honest-parse", "door": "parse_source", "direction": "reads"},
    ]
    failures = []
    for label, source, expected in (("mixed", mixed, expected_mixed), ("world only", only_world, [])):
        declaration = read_hd(source)["ok"]["modules"][0]
        actual = declared_seams(declaration)
        if actual != expected:
            failures.append(f"{label} declared seams -> {actual!r}, expected {expected!r}")
    return failures
