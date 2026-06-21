"""Behavior policy (section 4): what happens to a report is a table, looked up by environment.

`behaviors_for` is a pure dict lookup with a declared default (development). Adding an environment
or changing a policy is editing the table, never editing control flow. The list is data: the
composing boundary interprets each behavior — `log` goes to honest-observe, `email` to
honest-alerts, `reraise` to the boundary itself. honest-errors declares behaviors; it never runs
them.
"""

BEHAVIORS_BY_ENV = {
    "development": [{"name": "log", "order": 0}, {"name": "reraise", "order": 1}],
    "production": [{"name": "log", "order": 0}, {"name": "email", "order": 1}],
    "test": [{"name": "log", "order": 0}],
}


def behaviors_for(environment):
    """The ordered behaviors for an environment (section 4). Pure lookup; an unknown environment
    falls back to the development policy."""
    return BEHAVIORS_BY_ENV.get(environment, BEHAVIORS_BY_ENV["development"])
