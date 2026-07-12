"""The flag vocabulary and the flag state as a value (sections 2-3).

The vocabulary is static code: each flag declares its complete set of states and the initial value it
holds at startup. The flag state is ephemeral data, built from the vocabulary and threaded as a value —
never a module global — so `feature_state` stays a pure lookup and honest-features passes its own gate.
"""

from honest_type import err, fault, ok


# A flag entry carries exactly these two keys (section 2.1): no metadata leaks into the runtime vocabulary.
_FLAG_KEYS = {"states", "initial_value"}


def _flag_wellformed(spec):
    """Whether one flag entry obeys the vocabulary rules (section 2.1, section 10.2): exactly the keys
    `states` and `initial_value`, a `states` collection of at least two distinct members, and an
    `initial_value` that is one of them. Checks structure before contents, so a malformed entry is a clean
    False, never a KeyError. Pure."""
    if set(spec) != _FLAG_KEYS:
        return False
    states = spec["states"]
    if not isinstance(states, (list, set, tuple, frozenset)) or len(set(states)) < 2:
        return False
    return spec["initial_value"] in states


def validate_vocabulary(features):
    """Every flag entry obeys the vocabulary rules (section 2.1): exactly the keys `states` and
    `initial_value`, a `states` collection of at least two distinct members, and an `initial_value` that is
    one of them. Returns ok(features) or a client fault naming the offenders — a malformed entry is a clean
    fault, never a KeyError. Pure."""
    bad = [flag for flag, spec in features.items() if not _flag_wellformed(spec)]
    if bad:
        return err(fault("invalid_vocabulary", f"flags violate the vocabulary rules: {bad}", "client", detail=bad))
    return ok(features)


def initial_state(features):
    """The flag state at startup: each flag at its declared initial_value (section 3). Pure, no I/O. The
    application calls it once and holds the returned value."""
    return {flag: spec["initial_value"] for flag, spec in features.items()}


def feature_state(state, flag):
    """The current state of a flag, read from the state value (section 3). Pure lookup — a flag absent
    from the vocabulary is caught statically by HF001, so a flag reaching here is always present."""
    return state[flag]
