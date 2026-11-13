"""The bounded vocabularies (architecture section 2.1).

Each is a closed word-set, declared as a frozenset so honest-test can enumerate it and honest-check
treats it as a discriminant set. A report's severity, an environment, a behavior name, a suppression
reason and a payload source are each one of exactly these words, never a free string.
"""

SEVERITIES = frozenset({"debug", "info", "warning", "error", "critical"})

ENVIRONMENTS = frozenset({"development", "production", "test"})

BEHAVIOR_NAMES = frozenset({"log", "email"})

SUPPRESS_REASONS = frozenset({"rate_limit_hourly", "rate_limit_dedup"})

PAYLOAD_SOURCES = frozenset({"js", "py"})
