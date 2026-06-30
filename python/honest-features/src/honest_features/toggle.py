"""The toggle conditions and the state change as a value (sections 5.1, 5.3).

The toggle endpoint is polymorphic over the vocabulary: it does not know which flag it is setting. Both
of its checks and the change itself are pure functions over the vocabulary and the held state value; the
route is the integration boundary that holds the value, verifies the signature, and emits the event.
"""

from honest_type import err, fault, ok


def validate_toggle(features, flag, state):
    """The toggle request conditions (section 5.1): the flag must be declared and the state must be one
    of its declared states. Returns ok({flag, state}) or a client fault. Pure."""
    if flag not in features:
        return err(fault("unknown_flag", f"'{flag}' is not a declared flag", "client", detail=flag))
    if state not in features[flag]["states"]:
        return err(fault("invalid_state", f"'{state}' is not a state of '{flag}'", "client", detail=state))
    return ok({"flag": flag, "state": state})


def apply_toggle(current, flag, new):
    """Apply a state change as a value (section 5.3): the previous state and a new state value with the
    flag updated. Pure — `current` is not mutated, so the caller swaps in the returned value."""
    return {"previous": current[flag], "state": {**current, flag: new}}
