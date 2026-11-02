"""check_source folds the rule catalogue over one source's declaration graph and
returns findings as data: a class declaration fires HC-P003, a clean source is [].

Pins the function contract, not the per-rule specifics (those are suite.json's job):
findings come back as a list of Diagnostic, a class source carries an HC-P003
finding, and a clean source returns the empty list. It never raises for a violation.
"""

# A class declaration carries an HC-P003 finding; a clean assignment is clean.
# want_rule None is the explicit clean (absence) case: the empty list, written out.
_CASES = [
    {
        "given": {
            "source": "class Report:\n    pass\n",
            "path": "a.py",
            "rule_config": {},
            "declaration": None,
        },
        "want_rule": "HC-P003",
    },
    {
        "given": {
            "source": "x = 1\n",
            "path": "a.py",
            "rule_config": {},
            "declaration": None,
        },
        "want_rule": None,
    },
]


def _call_for(entry):
    """The call expression a watch-list entry becomes when placed in a link body: a `*`
    (the wildcard in `requests.*`, `os.spawn*`, `hashlib.*.hexdigest`) is filled with a
    concrete segment so the entry is a real dotted call, then called."""
    return f"{entry.replace('*', 'probe')}()"


def _watchlist_failures(check_source):
    """Spec §741 makes the watch list conformance-normative: every entry must be trapped.
    Because the match is one uniform membership test, prove completeness with a loop over
    watchlists.py — each Python IO and nondeterministic entry, placed as a call in a
    non-boundary link, must produce an HC008 finding."""
    from honest_check.watchlists import IO_WATCH_LIST, NONDETERMINISTIC_WATCH_LIST

    entries = sorted(IO_WATCH_LIST["python"] | NONDETERMINISTIC_WATCH_LIST["python"])
    bad = []
    for entry in entries:
        source = (
            "from honest_type import link\n"
            "@link()\n"
            "def probe_fn(manifest):\n"
            f"    return {_call_for(entry)}\n"
        )
        got = check_source(source, "watch.py", {}, None)
        rule_ids = [d.get("rule_id") for d in got]
        if "HC008" not in rule_ids:
            bad.append(
                f"watch-list entry {entry!r} placed as {_call_for(entry)!r} in a "
                f"non-boundary link produced {rule_ids}, expected an HC008 finding"
            )
    return bad


# ---- the boundary rules consult the module's .hd on the error path (honest-check.hd) ----
# check_source now takes a fourth argument: the parsed .hd for the file under check, or the
# absence value (Python None, the NOTHING arm) when the code has no .hd. A boundary rule
# here HC-P004, I/O inside a non-boundary function — decides boundary-ness from decorators,
# then, only on the path where it would fire, re-checks that same function against the
# declaration. When the .hd marks the function boundary_in/boundary_out/reader, the finding
# is dropped; with no declaration, or a non-door role, the decorator verdict stands.
_P004_SOURCE = "def save(path):\n    return open(path).read()\n"
_DOOR_HD = 'module m\n  boundary_in fn save : (path: str) -> str side_effect reads "filesystem"\n'
_PURE_HD = "module m\n  fn save : (path: str) -> str\n"

# want_p004 is the literal each case pins: does HC-P004 fire over this source under this
# declaration? False only when the .hd declares save a door. A stub check_source that
# returned [] would fail cases 2 and 3, so these cases are not vacuous.
_DECLARATION_CASES = [
    {
        "source": _P004_SOURCE,
        "hd": _DOOR_HD,
        "want_p004": False,
        "why": "the .hd marks save boundary_in, so the HC-P004 finding is dropped",
    },
    {
        "source": _P004_SOURCE,
        "hd": None,
        "want_p004": True,
        "why": "no .hd (the NOTHING arm), so the decorator verdict stands and HC-P004 fires",
    },
    {
        "source": _P004_SOURCE,
        "hd": _PURE_HD,
        "want_p004": True,
        "why": "the .hd marks save a pure fn, not a door, so HC-P004 still fires",
    },
]


def _declaration_for(hd_text):
    """The parsed .hd declaration honest-design's read_hd produces for a one-module .hd
    string, or None for the absence arm. honest-check receives this value already parsed;
    it never parses .hd itself (that is honest-design's job)."""
    if hd_text is None:
        return None
    from honest_design import read_hd

    return read_hd(hd_text)["ok"]["modules"][0]


def _declaration_failures(check_source):
    """The boundary rules consult the module's .hd on the error path and drop a boundary
    finding when the .hd declares that function a door; with no .hd (None) or a non-door
    role the finding stands (honest-check.hd, check_source's declaration argument). The
    verdict is read as the presence of the HC-P004 (rule_id, severity) pair, so the cases
    do not depend on source columns."""
    bad = []
    for case in _DECLARATION_CASES:
        declaration = _declaration_for(case["hd"])
        try:
            got = check_source(case["source"], "m.py", {}, declaration)
        except TypeError as exc:
            bad.append(
                f"check_source(<P004 source>, 'm.py', {{}}, declaration) raised {exc!r}; "
                "it does not yet accept the .hd declaration as a fourth argument"
            )
            continue
        if not isinstance(got, list):
            bad.append(f"check_source(<P004 source>, declaration) -> {got!r}, expected a list")
            continue
        pairs = {(d.get("rule_id"), d.get("severity")) for d in got}
        fired = any(rule_id == "HC-P004" for (rule_id, _severity) in pairs)
        if fired != case["want_p004"]:
            bad.append(
                f"check_source over the P004 source where {case['why']}: HC-P004 "
                f"{'fired' if fired else 'did not fire'} (pairs {sorted(pairs)}), "
                f"expected it to {'fire' if case['want_p004'] else 'be dropped'}"
            )
    return bad


def probe_check_source():
    try:
        from honest_check import check_source
    except ImportError as exc:
        return [f"cannot import check_source: {exc}"]

    bad = []
    for case in _CASES:
        got = check_source(**case["given"])
        if not isinstance(got, list):
            bad.append(f"check_source({case['given']}) -> {got!r}, expected a list")
            continue
        rule_ids = [d.get("rule_id") for d in got]
        if case["want_rule"] is None:
            if got != []:
                bad.append(
                    f"check_source({case['given']}) -> {got!r}, expected [] (clean source)"
                )
        elif case["want_rule"] not in rule_ids:
            bad.append(
                f"check_source({case['given']}) -> rule_ids {rule_ids}, "
                f"expected one to be {case['want_rule']!r}"
            )
    bad.extend(_watchlist_failures(check_source))
    bad.extend(_declaration_failures(check_source))
    return bad
