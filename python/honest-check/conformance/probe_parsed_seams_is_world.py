# scenario: _is_world identifies recognized world and resource targets
# inherits: hd=python/honest-check/honest-check.hd::_is_world -> feature=specs/features/honest-check.feature::_is_world identifies recognized world and resource targets


def probe_parsed_seams_is_world():
    from honest_check.seams import _is_world

    cases = (
        ("DOM", True), ("HTTP", True), ("file", True), ("env:POOL_SIZE", True),
        ("honest-persist", False), ("", False),
    )
    return [
        f"world {target!r} -> {actual!r}, expected {expected!r}"
        for target, expected in cases if (actual := _is_world(target)) is not expected
    ]
