"""The if-free dispatch primitive honest-persist's pure core reads a branch through.

honest-persist must pass its own checker (HC-P001), so its source carries no `if` statement: a
branch is a boolean key looked up in a closed two-row table. `_pick` is lazy — only the chosen
arm runs, so the other arm may build a fault, open nothing, or stay unevaluated.

A private copy of honest-type's `_util._pick`, not an import of it: the convention across the
framework is that each module carries its own copy of this primitive rather than reaching for a
sibling's private helper (honest-type/_util.py says the same of itself).
"""

_TWO_ROW = {True: lambda t, f: t, False: lambda t, f: f}


# Call and return when_true() when flag is truthy, else when_false(). Both arms are thunks,
# so only the chosen one runs.
_pick = lambda flag, when_true, when_false: _TWO_ROW[bool(flag)](when_true, when_false)()


# table[key] when key is a member of table, else make_default() — the open-key read guarded by
# its no-match row (P16). The subscript is on the `table` parameter, never on a module-level
# dispatch dict read by a bare variable key, so it carries no unguarded KeyError (HC-P020).
# make_default is a thunk, so the fallback — here a fault built only on a miss — never runs on a hit.
_read_or = lambda table, key, make_default: _pick(key in table, lambda: table[key], make_default)
