# scenario: _bare_seam keeps only a standalone bare module target
# inherits: hd=python/honest-check/honest-check.hd::_bare_seam -> feature=specs/features/honest-check.feature::_bare_seam keeps only a standalone bare module target


def probe_parsed_seams_bare_seam():
    from honest_check.seams import _bare_seam
    from honest_design import read_hd

    targets = ("", "file", "env:POOL_SIZE", "not a module", "honest-persist")
    expected_seam = {"caller": "save", "module": "honest-persist", "door": "", "direction": "writes"}
    failures = []
    for target in targets:
        hd = f'module sample\n\n  fn save : () -> any side_effect writes "{target}"\n'
        declaration = read_hd(hd)["ok"]["modules"][0]
        effect = declaration["functions"][0]["side_effects"][0]
        actual = _bare_seam("save", effect)
        expected = [expected_seam] if target == "honest-persist" else []
        if actual != expected:
            failures.append(f"bare {target!r} -> {actual!r}, expected {expected!r}")
    return failures
