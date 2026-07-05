"""Configuration (section 11): the honest-alerts config schema and its resolver.

The config is a TOML document (honest-alerts.toml) with five sections: the routing and delivery
honest-persist tables, the channel enablement, the DOM endpoints, and the send_and_wait default wait.
Reading and parsing the file is boundary I/O; resolving it is pure. resolve_config merges a parsed
config over ALERT_CONFIG_DEFAULTS section by section, so an omitted section or key keeps its default and
a provided value wins.
"""

# The section 11 defaults. A parsed config overrides these; anything it omits falls back here.
ALERT_CONFIG_DEFAULTS = {
    "routing": {"table": "alert_routes", "db_id": "primary"},
    "delivery": {"table": "alert_deliveries", "poll_interval_seconds": 5},
    "channels": {"dom": {"enabled": True}},
    "dom": {"sse_endpoint": "/api/alerts/stream", "reply_endpoint": "/api/alerts/{message_id}/reply"},
    "send_and_wait": {"default_ttl_seconds": 3600},
}


def resolve_config(raw):
    """Resolve a parsed config against the defaults (section 11). Pure: each declared section is the
    defaults for that section overlaid with the raw values, so provided keys win and omitted ones keep
    their default. Returns the resolved config with every section present."""
    return {section: {**defaults, **raw.get(section, {})} for section, defaults in ALERT_CONFIG_DEFAULTS.items()}
