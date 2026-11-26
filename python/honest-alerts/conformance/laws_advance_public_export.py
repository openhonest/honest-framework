# scenario: advance is available as an honest_alerts public export
# inherits: hd=python/honest-alerts/honest-alerts-pure.hd::advance -> feature=specs/features/honest-alerts.feature::advance is available as an honest_alerts public export
import honest_alerts


def probe_advance_public_export() -> list[str]:
    """Check the named public export and its callable package attribute."""
    failures = []
    if "advance" not in honest_alerts.__all__:
        failures.append("honest_alerts.__all__ omits advance")
    if not callable(getattr(honest_alerts, "advance", None)):
        failures.append("honest_alerts.advance is missing or not callable")
    return failures
