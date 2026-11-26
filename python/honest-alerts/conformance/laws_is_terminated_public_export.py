# scenario: is_terminated is available as an honest_alerts public export
# inherits: hd=python/honest-alerts/honest-alerts-pure.hd::is_terminated -> feature=specs/features/honest-alerts.feature::is_terminated is available as an honest_alerts public export
import honest_alerts


def probe_is_terminated_public_export() -> list[str]:
    """Check the named public export and its callable package attribute."""
    failures = []
    if "is_terminated" not in honest_alerts.__all__:
        failures.append("honest_alerts.__all__ omits is_terminated")
    if not callable(getattr(honest_alerts, "is_terminated", None)):
        failures.append("honest_alerts.is_terminated is missing or not callable")
    return failures
