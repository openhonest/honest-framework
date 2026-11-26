# scenario: _unknown_side_kind reports unknown world-side kinds
# inherits: hd=python/honest-design/honest-design.hd::_unknown_side_kind -> feature=python/honest-design/features/honest-design.feature::_unknown_side_kind reports unknown world-side kinds

_VALID = '''module example
  reader fn world : () -> str side_effect reads "clock" note "reads the clock"
  reader fn seam : () -> str side_effect reads "honest-parse.parse_source" note "uses the parser"
  fn held : () -> str side_effect reads "store:cache" note "reads held state"
'''
_UNKNOWN = '  reader fn typo : () -> str side_effect reads "filesystem:archive" note "bad kind"\n'
_CASES = [
    (_VALID, []),
    (_VALID + _UNKNOWN, [("unknown_side_kind", {"function": "typo", "target": "filesystem:archive", "kind": "filesystem"})]),
]


def probe_unknown_side_kind():
    from honest_design import read_hd
    from honest_design.validator import _unknown_side_kind

    failures = []
    for source, expected in _CASES:
        module = read_hd(source)["ok"]["modules"][0]
        actual = [(row["code"], row["detail"]) for row in _unknown_side_kind(module)]
        if actual != expected:
            failures.append(f"Expected {expected!r}, received {actual!r}")
    return failures
