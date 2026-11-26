# scenario: register_message_type is available as an honest_alerts public export
# inherits: hd=python/honest-alerts/honest-alerts.hd::register_message_type -> feature=specs/features/honest-alerts.feature::register_message_type is available as an honest_alerts public export
import honest_alerts


def probe_register_message_type_public_export() -> list[str]:
    """Check the named public export and its callable package attribute."""
    failures = []
    if "register_message_type" not in honest_alerts.__all__:
        failures.append("honest_alerts.__all__ omits register_message_type")
    if not callable(getattr(honest_alerts, "register_message_type", None)):
        failures.append("honest_alerts.register_message_type is missing or not callable")
    return failures
