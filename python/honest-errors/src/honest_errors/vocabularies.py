"""The four bounded vocabularies of honest-errors (spec section 2.1, .hd set declarations).

Each is a closed set of words, frozen so honest-test can enumerate it and honest-check can treat it
as a discriminant set. They are the words a report severity, a deployment environment, a named policy
behavior, and a throttle-suppression reason may each take.
"""

SEVERITIES = frozenset({"debug", "info", "warning", "error", "critical"})

ENVIRONMENTS = frozenset({"development", "production", "test"})

BEHAVIOR_NAMES = frozenset({"log", "email"})

SUPPRESS_REASONS = frozenset({"rate_limit_hourly", "rate_limit_dedup"})
