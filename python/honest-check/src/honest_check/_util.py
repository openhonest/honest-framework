"""If-free control primitives: the two-row dispatch tables that stand in for an
if/else. honest-check is the checker, so its own source carries no `if` statement;
a branch is a key computed and a value or a thunk looked up in a closed table
(P01). `pick` is lazy — only the chosen arm runs — and `choose` is eager, for arms
already safe to evaluate. `read_or` is the guarded open-key read (P16): it reads a
table by a key that may be absent, returning a named fallback without the silent
default `table.get(key, fallback)` files under a hit (P16, HC-P019)."""

_TWO_ROW = {True: lambda t, f: t, False: lambda t, f: f}


def pick(flag, when_true, when_false):
    """Call and return when_true() when flag is truthy, else when_false(). The two
    arms are thunks, so only the chosen one runs."""
    return _TWO_ROW[bool(flag)](when_true, when_false)()


def choose(flag, when_true, when_false):
    """Return when_true when flag is truthy, else when_false. Both arms are values
    already safe to evaluate."""
    return _TWO_ROW[bool(flag)](when_true, when_false)


def read_or(table, key, fallback):
    """table[key] when key is a member, else fallback — the open-key read guarded by
    its no-match row, never the default-filed-as-hit of table.get(key, fallback)."""
    return pick(key in table, lambda: table[key], lambda: fallback)
