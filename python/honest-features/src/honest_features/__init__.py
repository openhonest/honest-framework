"""honest-features: runtime-togglable feature flags with no rebuild, no redeploy (section 1).

A flag is a named state that routes execution to a handler. The flag vocabulary is static code; the flag
state is ephemeral data, threaded as a value and built from each flag's declared initial value. State changes go
through a single HMAC-signed toggle. honest-features ships pure functions only — the vocabulary checks,
the state value, the toggle conditions and change, the signature, and the honest-observe events. The HTTP
route, the secret loading, and the A/B middleware are integration boundaries that hold the state value
and read the clock; they do not live here.
"""

from honest_features.events import changed_event, evaluated_event
from honest_features.signature import build_signature, verify_signature
from honest_features.toggle import apply_toggle, validate_toggle
from honest_features.vocabulary import feature_state, initial_state, validate_vocabulary

__all__ = [
    "validate_vocabulary",
    "initial_state",
    "feature_state",
    "validate_toggle",
    "apply_toggle",
    "build_signature",
    "verify_signature",
    "changed_event",
    "evaluated_event",
]
