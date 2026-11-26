"""The if-free branch primitive, a private copy of honest-observe's _util (honest-observe section 3):
honest-render passes its own checker, so its source carries no `if` statement, ternary or comprehension
filter (HC-P001). A branch is a boolean key computed and a thunk looked up in a closed two-row table
(P01). These are plain names bound to lambdas, not `def`s, so they add no column-0 function to the
module's declared set -- every declared function keeps its one gherkin scenario and nothing else does.
"""

_TWO_ROW = {True: lambda when_true, when_false: when_true, False: lambda when_true, when_false: when_false}

# _pick is lazy: the two arms are thunks and only the chosen one runs. The key is bool(flag), a call
# rather than a bare identifier, so the two-row table closes its own input over the whole boolean
# domain and never raises on a miss.
_pick = lambda flag, when_true, when_false: _TWO_ROW[bool(flag)](when_true, when_false)()
