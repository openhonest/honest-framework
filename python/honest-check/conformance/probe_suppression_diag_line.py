# scenario: _diag_line reads the line from the right of a source location
# inherits: hd=python/honest-check/honest-check.hd::_diag_line -> feature=specs/features/honest-check.feature::_diag_line reads the line from the right of a source location


def probe_suppression_diag_line():
    from honest_check.rules import _diag_line

    cases = (("drive:folder/demo.py:17:4", 17), ("demo.py", None))
    return [
        f"location {path!r} -> {actual!r}, expected {expected!r}"
        for path, expected in cases
        if (actual := _diag_line({"rule_id": "HC-P004", "severity": "error", "message": "finding", "source_location": path, "context": "", "fixable": False})) != expected
    ]
