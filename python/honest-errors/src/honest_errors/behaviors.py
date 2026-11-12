"""Behavior policy (spec sections 3.1, 4). What should happen to a report is a list of named
behaviors, looked up by environment in a dispatch table. honest-errors declares the behaviors as data
and never executes them; the composing orchestrator interprets each one.
"""

from honest_type import fault

# The environment-to-behaviors dispatch table (spec section 4). Adding an environment or changing a
# policy is editing this table, never editing control flow.
BEHAVIORS_BY_ENV = {
    "development": [{"name": "log", "order": 0}],
    "production": [{"name": "log", "order": 0}, {"name": "email", "order": 1}],
    "test": [{"name": "log", "order": 0}],
}


def should_bypass_dedup(severity):
    """Tell whether a severity skips the throttle entirely (spec section 3.1): true only for critical,
    the one product rule, expressed as a predicate over data rather than control flow."""
    return severity == "critical"


def behaviors_for(environment):
    """Look up the ordered list of named behaviors for an environment, a pure dict lookup over
    BEHAVIORS_BY_ENV (spec section 4). An environment the table does not carry has no policy and yields
    an unknown_environment Fault that names the environment given and the environments accepted; it
    never falls back to another environment's policy."""
    if environment not in BEHAVIORS_BY_ENV:
        accepted = sorted(BEHAVIORS_BY_ENV)
        return fault(
            code="unknown_environment",
            message=f"environment {environment!r} has no policy; accepted environments are {accepted}",
            category="server",
            results=[],
            detail={"accepted": accepted, "arrived": environment},
        )
    return BEHAVIORS_BY_ENV[environment]
