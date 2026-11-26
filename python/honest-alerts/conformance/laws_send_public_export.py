# scenario: send is available as an honest_alerts public export
# inherits: hd=python/honest-alerts/honest-alerts.hd::send -> feature=specs/features/honest-alerts.feature::send is available as an honest_alerts public export
import honest_alerts


_EXPECTED = {
    "send",
    "acknowledge",
    "register_message_type",
    "advance",
    "mailbox",
    "is_terminated",
    "alert_tables_schema",
}


def probe_send_public_export() -> list[str]:
    """Check the declared public surface and an explicit internal import."""
    failures = []
    actual = honest_alerts.__all__
    if set(actual) != _EXPECTED or len(actual) != len(_EXPECTED):
        failures.append(
            f"honest_alerts.__all__ must contain exactly {sorted(_EXPECTED)!r}, got {actual!r}"
        )
    if not callable(getattr(honest_alerts, "send", None)):
        failures.append("honest_alerts.send is missing or not callable")
    try:
        from honest_alerts import build_message
    except ImportError as exc:
        failures.append(f"existing named import honest_alerts.build_message failed: {exc}")
    else:
        if not callable(build_message):
            failures.append("explicitly imported honest_alerts.build_message is not callable")
    return failures
