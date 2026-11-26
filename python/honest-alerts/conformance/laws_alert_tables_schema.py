# scenario: alert_tables_schema declares the required indexes and mutable tables
# inherits: hd=python/honest-alerts/honest-alerts-pure.hd::alert_tables_schema -> feature=specs/features/honest-alerts.feature::alert_tables_schema declares the required indexes and mutable tables
"""Check the three mutable Alerts table manifests, their columns, and their indexes."""

from honest_alerts import alert_tables_schema


# Columns the scenario fixes for each alerts-owned table (section 10b).
_EXPECTED = {
    "alert_routes": {
        "route_id",
        "message_type",
        "sender_type",
        "channels",
        "escalation",
        "priority",
    },
    "alert_deliveries": {
        "delivery_id",
        "message_id",
        "route_id",
        "channel",
        "recipient",
        "deliver_at",
        "status",
    },
    "alert_registered_types": {
        "message_type",
        "message_versions",
    },
}


_EXPECTED_INDEXES = {
    "alert_routes": {("message_type",)},
    "alert_deliveries": {("status", "deliver_at"), ("message_id",)},
    "alert_registered_types": set(),
}


def _column_names(entry):
    """Pull the column-name set out of one table manifest entry, tolerant of the
    container shape the scenario does not fix.

    Accepts either a mapping carrying a "columns" member (list of names, or list of
    {"name": ...} / {name: type} column records, or a {name: type} mapping) or a bare
    list/mapping of columns. Returns a set of column-name strings, or None when the
    entry does not present columns in any of these shapes."""
    cols = entry.get("columns") if isinstance(entry, dict) else entry
    if cols is None:
        return None
    if isinstance(cols, dict):
        return set(cols.keys())
    if isinstance(cols, (list, tuple)):
        names = set()
        for c in cols:
            if isinstance(c, str):
                names.add(c)
            elif isinstance(c, dict) and "name" in c:
                names.add(c["name"])
            elif isinstance(c, dict) and len(c) == 1:
                names.add(next(iter(c.keys())))
            else:
                return None
        return names
    return None


def _table_entries(manifest):
    """Retain each table record so its indexes and mutability can be checked."""
    if isinstance(manifest, dict):
        if "table" in manifest and "columns" in manifest:
            return {manifest["table"]: manifest}
        return manifest
    if isinstance(manifest, (list, tuple)):
        entries = {}
        for entry in manifest:
            if not isinstance(entry, dict) or "table" not in entry or entry["table"] in entries:
                return None
            entries[entry["table"]] = entry
        return entries
    return None


def _index_columns(entry):
    """Read ordered column paths from named secondary-index records."""
    indexes = entry.get("indexes")
    if not isinstance(indexes, (list, tuple)):
        return None

    paths = []
    for index in indexes:
        if not isinstance(index, dict):
            return None
        name = index.get("name")
        columns = index.get("columns")
        if not isinstance(name, str) or not name.strip():
            return None
        if not isinstance(columns, (list, tuple)) or not all(isinstance(col, str) for col in columns):
            return None
        paths.append(tuple(columns))
    return paths


def _schema_findings(manifest):
    """Return failures for a manifest missing declared schema facts."""
    tables = _table_entries(manifest)
    if tables is None or tables.keys() != _EXPECTED.keys():
        return [f"expected exactly the three Alerts table names, got {manifest!r}"]

    bad = []
    for name, expected_cols in _EXPECTED.items():
        entry = tables[name]
        if not isinstance(entry, dict):
            bad.append(f"{name} lacks a table record")
            continue
        columns = _column_names(entry)
        if columns is None or not expected_cols <= columns:
            bad.append(f"{name} has columns {columns!r}, expected at least {sorted(expected_cols)!r}")
        if entry.get("append_only") is not False:
            bad.append(f"{name} must explicitly declare append_only=False")
        actual_indexes = _index_columns(entry)
        expected_indexes = _EXPECTED_INDEXES[name]
        if actual_indexes is None or sorted(actual_indexes) != sorted(expected_indexes):
            bad.append(
                f"{name} has indexes {entry.get('indexes')!r}, expected named indexes "
                f"on the ordered columns {sorted(expected_indexes)!r}"
            )
    return bad


def probe_alert_tables_schema():
    """Read the actual manifest and check its declared structure."""
    return _schema_findings(alert_tables_schema())


if __name__ == "__main__":
    failures = probe_alert_tables_schema()
    if failures:
        for failure in failures:
            print("FAIL:", failure)
        raise SystemExit(1)
    print("ok")
