# scenario: alert_tables_schema is available as an honest_alerts public export
# inherits: hd=python/honest-alerts/honest-alerts-pure.hd::alert_tables_schema -> feature=specs/features/honest-alerts.feature::alert_tables_schema is available as an honest_alerts public export
import honest_alerts


def probe_alert_tables_schema_public_export() -> list[str]:
    """Check the named public export and its callable package attribute."""
    failures = []
    if "alert_tables_schema" not in honest_alerts.__all__:
        failures.append("honest_alerts.__all__ omits alert_tables_schema")
    if not callable(getattr(honest_alerts, "alert_tables_schema", None)):
        failures.append("honest_alerts.alert_tables_schema is missing or not callable")
    return failures
