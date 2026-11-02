"""check_auth folds the two identity rules over the whole set of code files and
returns the identity faults as data. This probe is the test-of-record for HC-A001
and HC-A002: both turn on project-wide provider registration (a provider registered
in any one file governs every authorizing link across the project), so neither can
be pinned by the single-source conformance suite the way check_source's per-file
rules are.

Each case builds its own small multi-file `sources` list inline, calls the real
check_auth over it, and checks the findings two ways: the set of
(rule_id, severity) pairs over the whole returned list equals the set the case
fixes, and every expected finding points at the offending file (its path appears in
the diagnostic's source_location), so a case does not depend on an exact column.

A stub returning [] passes the two clean cases (cases 2 and 4) but fails both firing
cases (1 and 3), so the probe is not vacuous.

Spec authorities: §HC-A001 (no provider registered while the set holds an authorizing
link, one warning) and §HC-A002 (a provider is registered and an authorizing link's
body does not reference the boundary-resolved actor, one error, section 8). The two
rules are mutually exclusive over one set: HC-A001 covers the no-provider case,
HC-A002 the with-provider case, so no authorizing link is ever reported by both.

Definitions the scenario fixes: a provider is registered when some file calls
register_auth_provider(...); an authorizing link is a top-level function decorated
@link(authorizes=True); a link uses the actor when its body references the name
`actor`.
"""

# Each case: a name, the multi-file sources list, and the findings it fixes as
# (rule_id, severity, offending_path) triples. The two clean cases fix the empty
# list, written out, because the scenario names them explicitly.
_CASES = [
    # HC-A002 fires — a provider is registered in file A, so the pass is in the
    # with-provider case; file B's authorizing link acts on behalf of an actor but
    # its body never references the name actor, so identity is sourced from request
    # input. One HC-A002 error points at file B, and no HC-A001 fires because a
    # provider is registered.
    {
        "name": "HC-A002 fires (authorizing link does not use actor, provider registered)",
        "sources": [
            {"path": "a.py", "text": "register_auth_provider(p)\n"},
            {
                "path": "b.py",
                "text": '@link(authorizes=True)\ndef pay(m):\n    return charge(m["amount"])\n',
            },
        ],
        "want": [("HC-A002", "error", "b.py")],
    },
    # HC-A002 clean — a provider is registered and the authorizing link's body
    # references the boundary-resolved actor, so identity flows inward as data.
    # Neither rule fires.
    {
        "name": "HC-A002 clean (authorizing link uses actor, provider registered)",
        "sources": [
            {"path": "a.py", "text": "register_auth_provider(p)\n"},
            {
                "path": "b.py",
                "text": '@link(authorizes=True)\ndef pay(m):\n    return charge(actor, m["amount"])\n',
            },
        ],
        "want": [],
    },
    # HC-A001 fires — no file registers a provider, and the set holds an authorizing
    # link, so the identity that link acts under is unverifiable. One HC-A001 warning
    # points at the link's file, and no HC-A002 fires because no provider is
    # registered (the two are mutually exclusive).
    {
        "name": "HC-A001 fires (authorizing link, no provider registered)",
        "sources": [
            {
                "path": "pay.py",
                "text": "@link(authorizes=True)\ndef pay(m):\n    return charge(m)\n",
            },
        ],
        "want": [("HC-A001", "warning", "pay.py")],
    },
    # Clean / no auth — a single file of plain functions, no authorizing link and no
    # provider registration, so neither rule has anything to fire on.
    {
        "name": "clean (no authorizing link, no registration)",
        "sources": [
            {"path": "m.py", "text": "def one(m):\n    return m\n\n\ndef two(m):\n    return m\n"},
        ],
        "want": [],
    },
]


def _pairs(findings):
    """The (rule_id, severity) set a run produced, as a sorted list for comparison."""
    return sorted((d.get("rule_id"), d.get("severity")) for d in findings)


def _want_pairs(want):
    """The (rule_id, severity) set a case fixes, as a sorted list."""
    return sorted((rule_id, severity) for rule_id, severity, _ in want)


def probe_check_auth():
    """check_auth reports one HC-A001 warning when no provider is registered and the
    set holds an authorizing link, reports one HC-A002 error at each authorizing
    link whose body does not reference the boundary-resolved actor when a provider
    is registered, points each finding at the offending file, and reports nothing
    when a provider is registered and every authorizing link uses the actor or when
    the set holds no authorizing link. The two rules never fire over the same set."""
    try:
        from honest_check import check_auth
    except ImportError as exc:
        return [f"cannot import check_auth: {exc}"]

    bad = []
    for case in _CASES:
        got = check_auth(case["sources"])
        if not isinstance(got, list):
            bad.append(f"{case['name']}: check_auth -> {got!r}, expected a list")
            continue

        got_pairs = _pairs(got)
        want_pairs = _want_pairs(case["want"])
        if got_pairs != want_pairs:
            bad.append(
                f"{case['name']}: (rule_id, severity) pairs {got_pairs}, "
                f"expected {want_pairs}"
            )

        for rule_id, severity, path in case["want"]:
            pointed = [
                d
                for d in got
                if d.get("rule_id") == rule_id
                and d.get("severity") == severity
                and path in str(d.get("source_location", ""))
            ]
            if not pointed:
                locations = [
                    (d.get("rule_id"), d.get("source_location")) for d in got
                ]
                bad.append(
                    f"{case['name']}: no {rule_id} {severity} finding points at "
                    f"{path!r}; findings were {locations}"
                )
    return bad
