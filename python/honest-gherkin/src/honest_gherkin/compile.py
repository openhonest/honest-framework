"""Pattern compilation (section 4): a step pattern becomes an anchored regex with named captures.

A pattern is a literal string with optional placeholders: `{name}` binds a string, `{name:type}`
binds and (at bind time) coerces. `PLACEHOLDER_TYPES` is the single source of truth for the
supported types — its regex fragment is used to build the match, its coercion is applied later by
match_step. An unknown type returns `err(StepFault bad_feature_syntax)`, never raised. The compiled
regex is anchored at both ends (full-text, not substring). The concrete regex dialect is the host's
(section 1.5).
"""

import re

from honest_type import err, ok

from honest_gherkin.ir import step_fault

# regex fragment + bind-time coercion per type. str/int/float are required; a spoke may add rows.
PLACEHOLDER_TYPES = {
    "str": {"regex": r'[^"]+', "coerce": str},
    "int": {"regex": r"[-+]?\d+", "coerce": int},
    "float": {"regex": r"[-+]?\d+\.\d+", "coerce": float},
}

_PLACEHOLDER = re.compile(r"\{(\w+)(?::(\w+))?\}")


def compile_pattern(pattern):
    """Compile a step pattern into a CompiledPattern (section 4). Pure. Returns ok(CompiledPattern),
    or err(StepFault bad_feature_syntax) for an unknown placeholder type."""
    parts = []
    captures = []
    cursor = 0
    for placeholder in _PLACEHOLDER.finditer(pattern):
        parts.append(re.escape(pattern[cursor:placeholder.start()]))
        name = placeholder.group(1)
        type_name = placeholder.group(2) or "str"
        if type_name not in PLACEHOLDER_TYPES:
            return err(step_fault("bad_feature_syntax", f"unknown placeholder type '{type_name}' in pattern: {pattern}"))
        parts.append(f"(?P<{name}>{PLACEHOLDER_TYPES[type_name]['regex']})")
        captures.append({"name": name, "type": type_name})
        cursor = placeholder.end()
    parts.append(re.escape(pattern[cursor:]))
    return ok({"regex": "^" + "".join(parts) + "$", "captures": captures})
