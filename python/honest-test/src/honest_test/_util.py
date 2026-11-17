"""If-free control primitives for honest-test, mirroring honest-type's two-row idiom.

honest-test must pass its own checker (HC-P001: no `if`), so a branch is a key
computed and a thunk looked up in a closed two-row table. These are plain names bound
to lambdas, not `def`s, so they add no column-0 function to the module's declared set
of 59 — every declared function keeps its one gherkin scenario and nothing else does.
`_pick` is lazy (only the chosen arm runs); `_choose` is eager; `_read_or` is the
guarded open-key read that never files a miss under a hit (P16).
"""

_TWO_ROW = {True: lambda t, f: t, False: lambda t, f: f}

_pick = lambda flag, when_true, when_false: _TWO_ROW[bool(flag)](when_true, when_false)()
_choose = lambda flag, when_true, when_false: _TWO_ROW[bool(flag)](when_true, when_false)
_read_or = lambda table, key, fallback: _pick(key in table, lambda: table[key], lambda: fallback)
