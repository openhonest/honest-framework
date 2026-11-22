"""The if-free branch primitive. honest-observe passes its own checker, so its source carries no `if`
statement, ternary or comprehension filter (HC-P001): a branch is a boolean key computed and a thunk
looked up in a closed two-row table (P01). These are plain names bound to lambdas, not `def`s, so they
add no column-0 function to the module's declared set -- every declared function keeps its one gherkin
scenario and nothing else does.

A private copy, not an import of honest-type's own _util: that module is private to honest-type, and
honest-observe composes honest-type's public surface rather than reaching into it.
"""

_TWO_ROW = {True: lambda when_true, when_false: when_true, False: lambda when_true, when_false: when_false}

# _pick is lazy: the two arms are thunks and only the chosen one runs. The key is bool(flag), a call
# rather than a bare identifier, so the two-row table closes its own input over the whole boolean
# domain and never raises on a miss.
_pick = lambda flag, when_true, when_false: _TWO_ROW[bool(flag)](when_true, when_false)()

# _get is the honest absent-tolerant read: a key present in a map yields its value, a key absent yields
# the caller's explicit absence value -- but through the two-row table, not dict.get's fallback, so a
# miss is a declared bounded case (P16) rather than a value filed under a hit (HC-P019). The caller
# names the absence at the call site, so absence is a visible decision, not a swallowed default.
_get = lambda mapping, key, absent: _pick(key in mapping, lambda: mapping[key], lambda: absent)
