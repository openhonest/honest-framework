# scenario: acknowledge is available as an honest_alerts public export
# inherits: hd=python/honest-alerts/honest-alerts.hd::acknowledge -> feature=specs/features/honest-alerts.feature::acknowledge is available as an honest_alerts public export
import honest_alerts


def probe_acknowledge_public_export() -> list[str]:
    """Check the named public export and its callable package attribute."""
    failures = []
    if "acknowledge" not in honest_alerts.__all__:
        failures.append("honest_alerts.__all__ omits acknowledge")
    if not callable(getattr(honest_alerts, "acknowledge", None)):
        failures.append("honest_alerts.acknowledge is missing or not callable")
    return failures
