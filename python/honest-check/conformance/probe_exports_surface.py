# scenario: __init__ publishes exactly its declared public surface in __all__
# inherits: hd=python/honest-check/honest-check.hd::__all__ -> feature=specs/features/honest-check.feature::__init__ publishes exactly its declared public surface
"""Verify that honest_check.__all__ is exactly its public surface and that every
name in it resolves to a real package attribute.

The package root re-exports the public surface so each probed function imports
from `honest_check` directly (§3.4). This probe pins that surface as data: the
exact set of names __all__ must carry, including the newest export
pure_target_is_callable. Blanking any one entry to "" (the constant_replace
mutant class) drops that name from the set and adds "" instead, so the set no
longer equals the expected set and the probe fails. Asserting each name resolves
via getattr also catches a declared name that binds nothing.
"""

# The public surface honest_check must publish, pinned literally. One name per
# line, mirroring the __all__ list in src/honest_check/__init__.py.
_EXPECTED_EXPORTS = {
    "HonestCheckError",
    "build_context",
    "check_source",
    "check_construction",
    "check_per_file",
    "apply_suppression",
    "startup_check",
    "check_paths",
    "run_check",
    "main",
    "check_seams",
    "pure_target_is_callable",
    "resolve_aliases",
}


def probe_exports_surface():
    """__all__ equals the expected public set and every entry resolves."""
    import honest_check

    failures = []

    declared = set(honest_check.__all__)
    if declared != _EXPECTED_EXPORTS:
        missing = _EXPECTED_EXPORTS - declared
        extra = declared - _EXPECTED_EXPORTS
        failures.append(
            f"honest_check.__all__ set {sorted(declared)} != expected "
            f"{sorted(_EXPECTED_EXPORTS)} (missing {sorted(missing)}, extra {sorted(extra)})"
        )

    for name in _EXPECTED_EXPORTS:
        if not hasattr(honest_check, name):
            failures.append(f"honest_check.__all__ names {name!r} but it is not an attribute of the package")

    return failures
