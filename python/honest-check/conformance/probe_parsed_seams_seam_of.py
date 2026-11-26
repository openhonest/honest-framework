# scenario: _seam_of preserves a qualified seam and skips an empty target
# inherits: hd=python/honest-check/honest-check.hd::_seam_of -> feature=specs/features/honest-check.feature::_seam_of preserves a qualified seam and skips an empty target


def probe_parsed_seams_seam_of():
    from honest_check.seams import _seam_of
    from honest_design import read_hd

    cases = (("honest-persist.open", "open"), ("honest-persist", ""), ("", None))
    failures = []
    for target, door in cases:
        hd = f'module sample\n\n  fn save : () -> any side_effect reads_writes "{target}"\n'
        declaration = read_hd(hd)["ok"]["modules"][0]
        effect = declaration["functions"][0]["side_effects"][0]
        actual = _seam_of("save", effect)
        expected = [] if door is None else [{"caller": "save", "module": "honest-persist", "door": door, "direction": "reads_writes"}]
        if actual != expected:
            failures.append(f"parsed {target!r} -> {actual!r}, expected {expected!r}")
    return failures
