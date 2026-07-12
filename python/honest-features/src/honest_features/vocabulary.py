"""The flag vocabulary and the flag state as a value (sections 2-3).

The vocabulary is static code: each flag declares its complete set of states and the initial value it
holds at startup. The flag state is ephemeral data, built from the vocabulary and threaded as a value —
never a module global — so `feature_state` stays a pure lookup and honest-features passes its own gate.
"""

from honest_type import err, fault, ok


def validate_vocabulary(features):
    """Every flag entry obeys the vocabulary rules (section 2.1): a `states` set of at least two members
    and an `initial_value` that is one of them. Returns ok(features) or a client fault naming the offenders. Pure."""
    bad = [flag for flag, spec in features.items() if len(spec["states"]) < 2 or spec["initial_value"] not in spec["states"]]
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
