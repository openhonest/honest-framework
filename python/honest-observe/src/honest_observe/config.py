"""Configuration (section 11, sections 9.5-9.6): the honest-observe.toml settings turned into data, and
the toggles read as pure functions of that data.

`load_config` is pure — a parsed toml dict in, a fully-defaulted, validated configuration out (as an
ok/err result, never an exception). Every documented key's default lives in one table, `_DEFAULTS`, which
the supplied values are merged over, so a missing key is resolved once here and never as a scattered
call-site fallback. `read_config` is the one I/O boundary: it reads and parses the file (a missing file is
the empty table, i.e. all defaults) and hands the dict to `load_config`.

The toggle resolvers (`development_mode`, `framework_event_enabled`, `include_manifests`,
`include_tracebacks`, `auto_tail`) are pure functions of the loaded configuration. Development mode is an
override layer (section 9.5): it forces classify events on, and the manifest, traceback, and auto-tail
conveniences each follow their own [development] sub-toggle. There is no `if DEBUG` anywhere — the decision
is data, the same wherever it is asked.
"""

import tomllib

from honest_type import err, fault, ok

# Section 11 / 9.6 — every documented key with its default, in one place. A loaded configuration is this
# shape with the supplied values merged over it; nothing else invents a fallback.
_DEFAULTS = {
    "event_log": {"table": "honest_event_log", "db_id": "primary", "retention_days": 365},
    "auth": {"provider": "honest-auth", "fields": []},
    "framework_events": {
        "chain_events": True,
        "link_events": True,
        "persist_events": True,
        "migration_events": True,
        "pool_events": True,
        "state_events": True,
        "classify_events": False,
    },
    "otel": {"enabled": False, "service": "", "environment": "production"},
    "snapshots": {"enabled": True, "default_interval": 1000, "storage_table": "honest_projection_snapshots"},
    "development": {"enabled": False, "auto_tail": False, "manifests": False, "tracebacks": False},
}

_AUTH_PROVIDERS = ("honest-auth", "custom", "none")


def _merged_section(name: str, raw: dict) -> dict:
    """One section merged: the defaults with the supplied values laid over the documented keys only, so an
    undocumented key resolves to its default rather than widening the shape. Pure."""
    supplied = raw.get(name, {})
    return {key: supplied.get(key, default) for key, default in _DEFAULTS[name].items()}


def load_config(raw: dict):
    """A parsed honest-observe.toml as a fully-defaulted, validated configuration (section 11). Pure.
    Returns ok(config) for a well-formed table, or err(fault 'invalid_config') when auth.provider is not
    one of the three providers, or is 'custom' with no fields."""
    config = {name: _merged_section(name, raw) for name in _DEFAULTS}
    provider = config["auth"]["provider"]
    if provider not in _AUTH_PROVIDERS:
        return err(fault("invalid_config", f"auth.provider must be one of honest-auth, custom, none; got '{provider}'", "client", {"provider": provider}))
    if provider == "custom" and not config["auth"]["fields"]:
        return err(fault("invalid_config", "auth.provider 'custom' requires a non-empty fields list", "client", {"provider": provider}))
    return ok(config)


def _read_text(path: str):
    """The toml file's parsed contents, or the empty table when the file is absent (section 11). I/O."""
    try:  # honest: ignore HC-P002: the config boundary reports a missing file as the empty (all-defaults) table rather than raising
        with open(path, "rb") as handle:  # honest: ignore HC-P004: the one I/O boundary of the config module — reading the settings file
            return tomllib.load(handle)
    except FileNotFoundError:
        return {}


def read_config(path: str):
    """Read, parse, and load the configuration file (section 11). The one I/O boundary: a missing file is
    the all-defaults configuration."""
    return load_config(_read_text(path))


def development_mode(config: dict) -> bool:
    """Whether development mode is active (section 9.5): the [development] enabled switch. Pure."""
    return config["development"]["enabled"]


def framework_event_enabled(config: dict, kind: str) -> bool:
    """Whether a framework event kind is emitted (section 11, 9.5). Pure. Reads the base framework_events
    toggle, except that development mode forces classify events on regardless of the base toggle."""
    base = config["framework_events"][f"{kind}_events"]
    return base or (kind == "classify" and development_mode(config))


def include_manifests(config: dict) -> bool:
    """Whether link and browser payloads carry manifest values (section 9.5). Pure: development mode and
    the [development] manifests sub-toggle."""
    return development_mode(config) and config["development"]["manifests"]


def include_tracebacks(config: dict) -> bool:
    """Whether error payloads carry tracebacks (section 9.5). Pure: development mode and the [development]
    tracebacks sub-toggle."""
    return development_mode(config) and config["development"]["tracebacks"]


def auto_tail(config: dict) -> bool:
    """Whether tail auto-streams to the terminal (section 9.5). Pure: development mode and the [development]
    auto_tail sub-toggle."""
    return development_mode(config) and config["development"]["auto_tail"]
