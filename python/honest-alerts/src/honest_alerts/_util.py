# bootstrap-exempt: the if-free branch primitive, the honest-observe _util precedent. These are
# plain names bound to lambdas, not column-0 `def`s, so they add no declared function to the module:
# every declared .hd function keeps its one gherkin scenario and nothing else does. A private copy,
# not an import of honest-type's own _util, because that module is private to honest-type.
"""The branch primitives honest-alerts composes from, so its source carries no `if` statement,
ternary or comprehension filter (HC-P001): a branch is a boolean key computed and a thunk looked up
in a closed two-row table (P01)."""

_TWO_ROW = {True: lambda when_true, when_false: when_true, False: lambda when_true, when_false: when_false}

# _pick is lazy: the two arms are thunks and only the chosen one runs. The key is bool(flag), a call
# rather than a bare identifier, so the two-row table closes its own input over the whole boolean
# domain and never raises on a miss.
_pick = lambda flag, when_true, when_false: _TWO_ROW[bool(flag)](when_true, when_false)()

# _get is the honest absent-tolerant read: a key present in a map yields its value, a key absent
# yields the caller's explicit absence value, through the two-row table rather than dict.get's
# fallback, so a miss is a declared bounded case (P16), not a value filed under a hit (HC-P019).
_get = lambda mapping, key, absent: _pick(key in mapping, lambda: mapping[key], lambda: absent)
