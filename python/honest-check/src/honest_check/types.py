"""honest-check's data records (honest-check.hd: types Diagnostic, RuleConfig).

Plain TypedDicts, the only class form the principles allow. A Diagnostic is one
finding from one rule against one place in the source; honest-check returns a
list of these and never throws for a violation, because a violation is data.
RuleConfig is the resolved per-rule settings, keyed by a configurable rule's id.
"""

from typing import TypedDict

# A RuleId is the catalogue identifier of the rule that fired (HC001, HC-P003,
# HC-REF005, ...). It is a str at the value level; the closed catalogue lives in
# the RuleId vocabulary in honest-check.hd.
RuleId = str

# The resolved per-rule settings: a configurable rule's id to that rule's named
# integer settings. load_config merges the project's honest-check.toml over the
# documented defaults at the boundary, so check_source always receives this
# complete, never a partial config.
RuleConfig = dict[str, dict[str, int]]


class Diagnostic(TypedDict):
    rule_id: RuleId
    severity: str
    message: str
    source_location: str
    context: str
    fixable: bool
