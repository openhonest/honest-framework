# scenario: mailbox is available as an honest_alerts public export
# inherits: hd=python/honest-alerts/honest-alerts-pure.hd::mailbox -> feature=specs/features/honest-alerts.feature::mailbox is available as an honest_alerts public export
import honest_alerts


def probe_mailbox_public_export() -> list[str]:
    """Check the named public export and its callable package attribute."""
    failures = []
    if "mailbox" not in honest_alerts.__all__:
        failures.append("honest_alerts.__all__ omits mailbox")
    if not callable(getattr(honest_alerts, "mailbox", None)):
        failures.append("honest_alerts.mailbox is missing or not callable")
    return failures
