"""matches_watchlist tests whether a dotted call name matches a watchlist entry
(honest-check.hd, spec section 3.5, HC008). It is the public counterpart of the membership
test HC008 runs against its I/O and non-determinism watch lists: honest-test calls it to
check its own non-determinism watch list against honest-check's, so the two tools trap
exactly the same calls (honest-test section 4.5).

An exact entry matches by equality; an entry carrying `*` matches as a glob — a trailing
`.*` names any attribute of a module, a trailing `*` is a prefix, a `*` between dots is one
segment. Pins the contract: exact and each glob shape match, and a name on no entry (or an
empty watch list) does not. A stub returning False fails the match cases; one returning
True fails the no-match cases; so the probe is not vacuous either way.
"""

_CASES = [
    {"name": "time.time", "watchlist": ["time.time"], "want": True},
    {"name": "requests.get", "watchlist": ["requests.*"], "want": True},
    {"name": "os.spawnvp", "watchlist": ["os.spawn*"], "want": True},
    {"name": "hashlib.sha256.hexdigest", "watchlist": ["hashlib.*.hexdigest"], "want": True},
    {"name": "os.getpid", "watchlist": ["time.*", "random.random"], "want": False},
    {"name": "time.time", "watchlist": [], "want": False},
]


def probe_matches_watchlist():
    try:
        from honest_check.watchlists import matches_watchlist
    except ImportError as exc:
        return [f"cannot import matches_watchlist from honest_check.watchlists: {exc}"]

    bad = []
    for case in _CASES:
        got = matches_watchlist(case["name"], case["watchlist"])
        if got != case["want"]:
            bad.append(
                f"matches_watchlist({case['name']!r}, {case['watchlist']!r}) -> {got!r}, "
                f"expected {case['want']!r}"
            )
    return bad
