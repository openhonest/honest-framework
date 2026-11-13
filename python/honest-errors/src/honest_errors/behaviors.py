"""Behavior policy (architecture section 4).

What should happen to a report is a list of named behaviors, looked up by environment through a dict,
not an if/elif ladder. An environment the table does not carry has no policy, so behaviors_for returns
an unknown_environment Fault; it never falls back to another environment's policy.
"""

from honest_errors.vocabularies import ENVIRONMENTS

# The environment-to-behaviors policy table (section 4). Adding an environment or changing a policy is
# editing this table, never editing control flow. The behaviors are data the composing caller
# interprets (log to honest-observe, email to honest-alerts); honest-errors never executes them.
BEHAVIORS_BY_ENV = {
    "development": [{"name": "log", "order": 0}],
    "production": [{"name": "log", "order": 0}, {"name": "email", "order": 1}],
    "test": [{"name": "log", "order": 0}],
}


def behaviors_for(environment):
    """Look up the behaviors for an environment (section 4): [log] for development and test,
    [log, email] for production. An environment the table does not carry returns an unknown_environment
    Fault whose message names the environment given and the environments accepted."""
    if environment not in BEHAVIORS_BY_ENV:
        accepted = sorted(ENVIRONMENTS)
        return {
            "code": "unknown_environment",
            "message": f"environment {environment!r} has no policy; accepted environments are {accepted}",
        }
    return BEHAVIORS_BY_ENV[environment]
