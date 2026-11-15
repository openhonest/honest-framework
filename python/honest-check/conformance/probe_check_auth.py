"""Honest probe for honest-check's check_auth (feature Scenario: check_auth).

check_auth runs the two whole-program identity rules over the project's code as one set. A
provider is registered when some file calls register_auth_provider; an authorizing link is a
function decorated @link(authorizes=True). HC-A001 emits one warning when no provider is
registered and the set holds at least one authorizing link; HC-A002 emits one error per
authorizing link whose body does not reference the boundary-resolved name actor when a
provider is registered; the two are mutually exclusive over the set.

Four cases:
- no provider, one authorizing link -> one HC-A001 warning;
- a provider registered, one authorizing link whose body never names actor -> one HC-A002 error;
- a provider registered, one authorizing link that references actor -> no finding;
- the explicit none case: no provider and no authorizing link -> no finding.

A `return []` stub passes the two empty cases and fails the HC-A001 and HC-A002 cases. The
package is real: pair_source joins each path to its bytes into a SourceFile. No fabricated nodes.
"""

# No register_auth_provider call; one @link(authorizes=True) link.
_A001_SOURCE = (
    b"@link(authorizes=True)\n"
    b"def do_thing(actor):\n"
    b"    return actor\n"
)

# A provider is registered; the authorizing link's body never references actor.
_A002_SOURCE = (
    b"register_auth_provider(my_provider)\n"
    b"\n"
    b"@link(authorizes=True)\n"
    b"def do_thing(request):\n"
    b"    return request\n"
)

# A provider is registered; the authorizing link references actor.
_CLEAN_SOURCE = (
    b"register_auth_provider(my_provider)\n"
    b"\n"
    b"@link(authorizes=True)\n"
    b"def do_thing(actor):\n"
    b"    return actor\n"
)

# No provider and no authorizing link at all.
_NONE_SOURCE = (
    b"def plain():\n"
    b"    return 1\n"
)

# Each case: the project's code (bytes), the rule_id that must appear, and the total finding count.
_CASES = [
    {"desc": "no provider with an authorizing link warns HC-A001", "source": _A001_SOURCE, "must_contain": "HC-A001", "expect_total": 1},
    {"desc": "a provider with an actor-less authorizing link errors HC-A002", "source": _A002_SOURCE, "must_contain": "HC-A002", "expect_total": 1},
    {"desc": "a provider with an actor-using link is clean", "source": _CLEAN_SOURCE, "must_contain": None, "expect_total": 0},
    {"desc": "no provider and no authorizing link is clean", "source": _NONE_SOURCE, "must_contain": None, "expect_total": 0},
]


def probe_check_auth():
    """check_auth warns HC-A001 with no provider, errors HC-A002 on an actor-less link, else is silent."""
    try:
        from honest_check import check_auth, pair_source
    except ImportError as exc:
        return [f"cannot import check_auth: {exc}"]

    bad = []
    for case in _CASES:
        sources = [pair_source(path="svc.py", text=case["source"])]
        got = check_auth(sources=sources)
        ids = [d["rule_id"] for d in got]
        if len(got) != case["expect_total"]:
            bad.append(
                f"check_auth({case['desc']}) -> {ids}, expected {case['expect_total']} finding(s)"
            )
        elif case["must_contain"] is not None and case["must_contain"] not in ids:
            bad.append(
                f"check_auth({case['desc']}) -> {ids}, expected a {case['must_contain']} finding"
            )
    return bad
