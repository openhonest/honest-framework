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
    # A path whose extension honest-parse does not place yields a parse result whose
    # code is not syntax_error, so check_source has no architecture to check and returns
    # the empty list, distinct from the HC-SYN a real syntax error produces.
    {
        "given": {
            "source": "x = 1\n",
            "path": "a.bin",
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


# ---- HC-ST001 consults the module's .hd on the error path, like the other boundary rules ----
# HC-ST001 fires on a honest-persist write (transaction/apply) in a non-boundary function. It
# reuses the same boundary machinery HC-P004 uses, so the .hd consult applies identically: when
# the .hd marks the enclosing function boundary_in/boundary_out/reader, the write is the
# legitimate boundary write and the finding is dropped; with no .hd, or a pure-fn role, it fires.
_ST001_SOURCE = "from honest_persist import transaction\ndef save(rows, conn):\n    return transaction(rows, conn)\n"
_ST001_DOOR_HD = 'module m\n  boundary_out fn save : (rows: list<any>, conn: any) -> any side_effect writes "database"\n'
_ST001_PURE_HD = "module m\n  fn save : (rows: list<any>, conn: any) -> any\n"

_ST001_DECLARATION_CASES = [
    {
        "source": _ST001_SOURCE,
        "hd": _ST001_DOOR_HD,
        "want_st001": False,
        "why": "the .hd marks save boundary_out, so the persisted-state write is the legitimate boundary write and HC-ST001 is dropped",
    },
    {
        "source": _ST001_SOURCE,
        "hd": None,
        "want_st001": True,
        "why": "no .hd (the NOTHING arm), so save is a non-boundary function and HC-ST001 fires",
    },
    {
        "source": _ST001_SOURCE,
        "hd": _ST001_PURE_HD,
        "want_st001": True,
        "why": "the .hd marks save a pure fn, not a door, so HC-ST001 still fires",
    },
]


def _st001_declaration_failures(check_source):
    """HC-ST001 drops its finding when the .hd declares the enclosing function a door, and
    fires with no .hd or a non-door role. Read as the presence of the HC-ST001 rule_id, so
    the cases do not depend on source columns."""
    bad = []
    for case in _ST001_DECLARATION_CASES:
        declaration = _declaration_for(case["hd"])
        got = check_source(case["source"], "m.py", {}, declaration)
        fired = any(d.get("rule_id") == "HC-ST001" for d in got)
        if fired != case["want_st001"]:
            bad.append(
                f"check_source over the ST001 source where {case['why']}: HC-ST001 "
                f"{'fired' if fired else 'did not fire'}, expected it to "
                f"{'fire' if case['want_st001'] else 'be dropped'}"
            )
    return bad


# ---- HC-OR003, suspected duplication between orchestrators (section 3.1, §HC-OR003) ----
# A soft warning: two orchestrators that share a run of min_run or more consecutive equivalent
# calls. min_run has no built-in default and reaches check_source only through rule_config, so
# the rule runs only when a project sets [rules.HC-OR003] min_run. These cases pass that config
# directly, which the single-source suite (always an empty config) cannot, so they live here.
_OR003_SHARED = (
    "@orchestrator\n"
    "def flow_a(x):\n"
    "    a = step_one(x)\n"
    "    b = step_two(a)\n"
    "    c = step_three(b)\n"
    "    return c\n"
    "@orchestrator\n"
    "def flow_b(x):\n"
    "    a = step_one(x)\n"
    "    b = step_two(a)\n"
    "    c = step_three(b)\n"
    "    return other(c)\n"
)
_OR003_SHORT = (
    "@orchestrator\n"
    "def flow_a(x):\n"
    "    a = step_one(x)\n"
    "    b = step_two(a)\n"
    "    return b\n"
    "@orchestrator\n"
    "def flow_b(x):\n"
    "    a = step_one(x)\n"
    "    b = step_two(a)\n"
    "    return other(b)\n"
)
# A shared sequence that repeats a call name, so the longest-run dynamic program meets a
# later match that does not beat the best run already found: flow_a and flow_b both call
# step_one, step_two, step_one. The shared run is two (step_one, step_two), and the trailing
# step_one match does not extend it.
_OR003_REPEAT = (
    "@orchestrator\n"
    "def flow_a(x):\n"
    "    a = step_one(x)\n"
    "    b = step_two(a)\n"
    "    c = step_one(b)\n"
    "    return c\n"
    "@orchestrator\n"
    "def flow_b(x):\n"
    "    a = step_one(x)\n"
    "    b = step_two(a)\n"
    "    c = step_one(b)\n"
    "    return other(c)\n"
)
_OR003_CASES = [
    {"source": _OR003_SHARED, "rule_config": {"HC-OR003": {"min_run": 3}}, "want": True,
     "why": "two orchestrators share a run of three consecutive calls and min_run is 3"},
    {"source": _OR003_SHARED, "rule_config": {}, "want": False,
     "why": "min_run is not set, so HC-OR003 does not run at all"},
    {"source": _OR003_SHORT, "rule_config": {"HC-OR003": {"min_run": 3}}, "want": False,
     "why": "the shared run is only two calls, below min_run 3"},
    {"source": _OR003_REPEAT, "rule_config": {"HC-OR003": {"min_run": 2}}, "want": True,
     "why": "the shared run of two repeats a call name, so a later match does not beat the best run"},
]


def _or003_failures(check_source):
    """HC-OR003 warns when two orchestrators share a run of min_run or more consecutive
    equivalent calls, and runs only when min_run is set in rule_config. Read as the presence
    of an HC-OR003 finding, so the cases do not depend on source columns."""
    bad = []
    for case in _OR003_CASES:
        got = check_source(case["source"], "o.py", case["rule_config"], None)
        fired = any(d.get("rule_id") == "HC-OR003" for d in got)
        if fired != case["want"]:
            bad.append(
                f"check_source over the two-orchestrator source where {case['why']}: "
                f"HC-OR003 {'fired' if fired else 'did not fire'}, expected it to "
                f"{'fire' if case['want'] else 'not fire'}"
            )
    return bad


# ---- full-record pinning (section 9.2) ----
_MSG_CASES = [
    {
        "id": 'HC003-set',
        "source": 'x = vocabulary({"t1": {"v"}, "t2": {"v"}})\n',
        "rule_config": {},
        "hd": None,
        "expected": [{'rule_id': 'HC003', 'severity': 'error', 'message': "Types 't1' and 't2' share values: ['v']", 'source_location': 'case_HC003-set.py:1:5', 'context': 'vocabulary({"t1": {"v"}, "t2": {"v"}})', 'fixable': False}],
    },
    {
        "id": 'HC003-info-HC009-HC011',
        "source": "from honest_type import vocabulary\nx = vocabulary({'t1': {'v'}, 't2': lambda s: int(s)})\n",
        "rule_config": {},
        "hd": None,
        "expected": [{'rule_id': 'HC003', 'severity': 'info', 'message': "Types 't1' and 't2' may overlap on a value — verified by honest-test", 'source_location': 'case_HC003-info-HC009-HC011.py:2:5', 'context': "vocabulary({'t1': {'v'}, 't2': lambda s: int(s)})", 'fixable': False}, {'rule_id': 'HC009', 'severity': 'warning', 'message': "Predicate recognizer 't2' may throw on non-matching input. Wrap in try/except or guard with isinstance() — verified by honest-test.", 'source_location': 'case_HC003-info-HC009-HC011.py:2:5', 'context': "vocabulary({'t1': {'v'}, 't2': lambda s: int(s)})", 'fixable': False}, {'rule_id': 'HC011', 'severity': 'info', 'message': "Predicate recognizer 't2' may be a catch-all — verified by honest-test", 'source_location': 'case_HC003-info-HC009-HC011.py:2:5', 'context': "vocabulary({'t1': {'v'}, 't2': lambda s: int(s)})", 'fixable': False}],
    },
    {
        "id": 'HC006-requires',
        "source": "from honest_type import vocabulary, composed\nx = vocabulary({'a': {'1'}}, composed_types=[composed('c', {'missing': {}})])\n",
        "rule_config": {},
        "hd": None,
        "expected": [{'rule_id': 'HC006', 'severity': 'error', 'message': "Composed type requires unknown base type 'missing'", 'source_location': 'case_HC006-requires.py:2:46', 'context': "composed('c', {'missing': {}})", 'fixable': False}],
    },
    {
        "id": 'HC006-captures',
        "source": "from honest_type import vocabulary, composed\nx = vocabulary({'a': {'1'}}, composed_types=[composed('c', {'a': {}}, 'nope')])\n",
        "rule_config": {},
        "hd": None,
        "expected": [{'rule_id': 'HC006', 'severity': 'error', 'message': "Composed type captures unknown base type 'nope'", 'source_location': 'case_HC006-captures.py:2:46', 'context': "composed('c', {'a': {}}, 'nope')", 'fixable': False}],
    },
    {
        "id": 'HC007',
        "source": 'x = chain()\n',
        "rule_config": {},
        "hd": None,
        "expected": [{'rule_id': 'HC007', 'severity': 'error', 'message': 'Chain has no links', 'source_location': 'case_HC007.py:1:5', 'context': 'chain()', 'fixable': False}],
    },
    {
        "id": 'HC-SM01',
        "source": 'm = state_machine({"a"}, {"e"}, {("bad", "e"): "a"}, "a", terminal={"a"})\n',
        "rule_config": {},
        "hd": None,
        "expected": [{'rule_id': 'HC-SM01', 'severity': 'error', 'message': "State 'bad' in transition table not in states vocabulary", 'source_location': 'case_HC-SM01.py:1:5', 'context': 'state_machine({"a"}, {"e"}, {("bad", "e"): "a"}, "a", terminal={"a"})', 'fixable': False}],
    },
    {
        "id": 'HC-SM02',
        "source": 'm = state_machine({"a"}, {"e"}, {("a", "bad"): "a"}, "a", terminal={"a"})\n',
        "rule_config": {},
        "hd": None,
        "expected": [{'rule_id': 'HC-SM02', 'severity': 'error', 'message': "Event 'bad' in transition table not in events vocabulary", 'source_location': 'case_HC-SM02.py:1:5', 'context': 'state_machine({"a"}, {"e"}, {("a", "bad"): "a"}, "a", terminal={"a"})', 'fixable': False}],
    },
    {
        "id": 'HC-SM03',
        "source": 'm = state_machine({"a", "b", "c"}, {"e"}, {("a", "e"): "b"}, "a", terminal={"b"})\n',
        "rule_config": {},
        "hd": None,
        "expected": [{'rule_id': 'HC-SM03', 'severity': 'warning', 'message': "State 'c' is unreachable", 'source_location': 'case_HC-SM03.py:1:5', 'context': 'state_machine({"a", "b", "c"}, {"e"}, {("a", "e"): "b"}, "a", terminal={"b"})', 'fixable': False}, {'rule_id': 'HC-SM04', 'severity': 'warning', 'message': "State 'c' has no outgoing transitions and is not declared terminal", 'source_location': 'case_HC-SM03.py:1:5', 'context': 'state_machine({"a", "b", "c"}, {"e"}, {("a", "e"): "b"}, "a", terminal={"b"})', 'fixable': False}],
    },
    {
        "id": 'HC-SM04',
        "source": 'm = state_machine({"a", "b"}, {"e"}, {("a", "e"): "b"}, "a")\n',
        "rule_config": {},
        "hd": None,
        "expected": [{'rule_id': 'HC-SM04', 'severity': 'warning', 'message': "State 'b' has no outgoing transitions and is not declared terminal", 'source_location': 'case_HC-SM04.py:1:5', 'context': 'state_machine({"a", "b"}, {"e"}, {("a", "e"): "b"}, "a")', 'fixable': False}],
    },
    {
        "id": 'HC-SM05',
        "source": 'm = state_machine({"a"}, {"e"}, {("a", "e"): "a"}, "zzz", terminal={"a"})\n',
        "rule_config": {},
        "hd": None,
        "expected": [{'rule_id': 'HC-SM05', 'severity': 'error', 'message': "Initial state 'zzz' not in states vocabulary", 'source_location': 'case_HC-SM05.py:1:5', 'context': 'state_machine({"a"}, {"e"}, {("a", "e"): "a"}, "zzz", terminal={"a"})', 'fixable': False}, {'rule_id': 'HC-SM03', 'severity': 'warning', 'message': "State 'a' is unreachable", 'source_location': 'case_HC-SM05.py:1:5', 'context': 'state_machine({"a"}, {"e"}, {("a", "e"): "a"}, "zzz", terminal={"a"})', 'fixable': False}],
    },
    {
        "id": 'HC-P003-nobase',
        "source": 'class A:\n    pass\n',
        "rule_config": {},
        "hd": None,
        "expected": [{'rule_id': 'HC-P003', 'severity': 'error', 'message': "Class 'A' has no declared base. Use a TypedDict for data shapes or a pure function.", 'source_location': 'case_HC-P003-nobase.py:1:1', 'context': 'class A:', 'fixable': False}],
    },
    {
        "id": 'HC-P003-inherits',
        "source": 'class A(Foo):\n    pass\n',
        "rule_config": {},
        "hd": None,
        "expected": [{'rule_id': 'HC-P003', 'severity': 'error', 'message': "Class 'A' inherits from 'Foo'. Use composition over inheritance.", 'source_location': 'case_HC-P003-inherits.py:1:1', 'context': 'class A(Foo):', 'fixable': False}],
    },
    {
        "id": 'HC-P001',
        "source": 'def f(x):\n    if x == 1:\n        return 1\n    elif x == 2:\n        return 2\n    elif x == 3:\n        return 3\n',
        "rule_config": {},
        "hd": None,
        "expected": [{'rule_id': 'HC-P001', 'severity': 'error', 'message': 'if/elif/else chain dispatches on value — use dict lookup. See honest-code-principles.md §3.', 'source_location': 'case_HC-P001.py:2:5', 'context': 'if x == 1:', 'fixable': False}],
    },
    {
        "id": 'HC-P007',
        "source": 'class C:\n    def __init__(self):\n        self._x = 1\n',
        "rule_config": {},
        "hd": None,
        "expected": [{'rule_id': 'HC-P003', 'severity': 'error', 'message': "Class 'C' has no declared base. Use a TypedDict for data shapes or a pure function.", 'source_location': 'case_HC-P007.py:1:1', 'context': 'class C:', 'fixable': False}, {'rule_id': 'HC-P007', 'severity': 'warning', 'message': "Instance state '_x'. Pass as parameter or use context manager.", 'source_location': 'case_HC-P007.py:3:9', 'context': 'self._x = 1', 'fixable': False}],
    },
    {
        "id": 'HC-P011',
        "source": 'useEffect()\n',
        "rule_config": {},
        "hd": None,
        "expected": [{'rule_id': 'HC-P011', 'severity': 'error', 'message': "Lifecycle hook 'useEffect'. Use HTMX attributes or server-rendered HTML.", 'source_location': 'case_HC-P011.py:1:1', 'context': 'useEffect()', 'fixable': False}],
    },
    {
        "id": 'HC-P016',
        "source": 'def outer():\n    acc = 0\n    def inner():\n        nonlocal acc\n        acc = acc + 1\n    return inner\n',
        "rule_config": {},
        "hd": None,
        "expected": [{'rule_id': 'HC-P016', 'severity': 'error', 'message': "Inner function 'inner' captures 'acc' via nonlocal and mutates it. Closures may not carry mutable state — use pure parameters or move state into persist.", 'source_location': 'case_HC-P016.py:3:5', 'context': 'def inner():', 'fixable': False}],
    },
    {
        "id": 'HC-P002',
        "source": 'def f(x):\n    try:\n        return x\n    except Exception:\n        return None\n',
        "rule_config": {},
        "hd": None,
        "expected": [{'rule_id': 'HC-P002', 'severity': 'error', 'message': "Function 'f' catches an exception in business logic. Let the function raise; catch at the boundary (@boundary / route handler), or return a fault as data.", 'source_location': 'case_HC-P002.py:2:5', 'context': 'try:', 'fixable': False}],
    },
    {
        "id": 'HC-P004',
        "source": 'def f(p):\n    return open(p)\n',
        "rule_config": {},
        "hd": None,
        "expected": [{'rule_id': 'HC-P004', 'severity': 'error', 'message': "I/O call 'open' in a non-boundary function reaches outside the process off the boundary. Do the I/O at a boundary (@boundary / route handler) and pass the result into the pure interior.", 'source_location': 'case_HC-P004.py:2:12', 'context': 'open(p)', 'fixable': False}],
    },
    {
        "id": 'HC-ST001',
        "source": 'from honest_persist import transaction\ndef save(rows, conn):\n    return transaction(rows, conn)\n',
        "rule_config": {},
        "hd": None,
        "expected": [{'rule_id': 'HC-ST001', 'severity': 'error', 'message': "Persisted-state write 'transaction' in a non-boundary function writes the database off the boundary. Do the write at a boundary (@boundary / route handler), not in the pure interior.", 'source_location': 'case_HC-ST001.py:3:12', 'context': 'transaction(rows, conn)', 'fixable': False}],
    },
    {
        "id": 'HC-P005',
        "source": 'def f(x):\n    return isinstance(x, int)\n',
        "rule_config": {},
        "hd": None,
        "expected": [{'rule_id': 'HC-P005', 'severity': 'warning', 'message': 'Runtime type check in business logic. Declare the constraint as a vocabulary at the boundary instead.', 'source_location': 'case_HC-P005.py:2:12', 'context': 'isinstance(x, int)', 'fixable': False}],
    },
    {
        "id": 'HC-P006',
        "source": '@lru_cache\ndef a():\n    return 1\n',
        "rule_config": {},
        "hd": None,
        "expected": [{'rule_id': 'HC-P006', 'severity': 'warning', 'message': "Cache decorator without a profiling note. Add a @profiled decorator or a '# honest: profiled' comment proving the cache was measured.", 'source_location': 'case_HC-P006.py:1:1', 'context': '@lru_cache', 'fixable': False}],
    },
    {
        "id": 'HC-P015',
        "source": 'def f(x=5):\n    return x\n',
        "rule_config": {},
        "hd": None,
        "expected": [{'rule_id': 'HC-P015', 'severity': 'error', 'message': "Parameter 'x' defaults to a real value. A default hides whether the caller chose the value or omitted it, and leaves the omitted-argument path untested. Make the parameter required, or default it to empty if absence is the honest nothing.", 'source_location': 'case_HC-P015.py:1:7', 'context': 'x=5', 'fixable': False}],
    },
    {
        "id": 'HC008',
        "source": 'from honest_type import link\ng = []\n@link()\ndef rd(m):\n    return g\n',
        "rule_config": {},
        "hd": None,
        "expected": [{'rule_id': 'HC008', 'severity': 'warning', 'message': "Link 'rd' may be impure: it calls a watched function or reads module-level mutable state. Add boundary=True if the I/O is intentional.", 'source_location': 'case_HC008.py:4:1', 'context': 'def rd(m):', 'fixable': False}],
    },
    {
        "id": 'HC001',
        "source": 'from honest_type import chain\ndef step(x):\n    return x\nc = chain(step)\n',
        "rule_config": {},
        "hd": None,
        "expected": [{'rule_id': 'HC001', 'severity': 'error', 'message': "Chain link 'step' has no vocabulary declared. Wrap it with @link(accepts=..., emits=...) or the link() constructor.", 'source_location': 'case_HC001.py:4:5', 'context': 'chain(step)', 'fixable': False}],
    },
    {
        "id": 'HC-OR001',
        "source": '@orchestrator\ndef flow_a(x):\n    return flow_b(x)\n@orchestrator\ndef flow_b(x):\n    return x\n',
        "rule_config": {},
        "hd": None,
        "expected": [{'rule_id': 'HC-OR001', 'severity': 'error', 'message': "Orchestrator 'flow_a' calls orchestrator 'flow_b'. Orchestrators are the root of an operation and do not compose. Extract the shared logic as a pure helper (if no I/O) or as a chain (if I/O is involved).", 'source_location': 'case_HC-OR001.py:3:12', 'context': 'flow_b(x)', 'fixable': False}],
    },
    {
        "id": 'HC-OR003',
        "source": '@orchestrator\ndef flow_a(x):\n    a = step_one(x)\n    b = step_two(a)\n    c = step_three(b)\n    return c\n@orchestrator\ndef flow_b(x):\n    a = step_one(x)\n    b = step_two(a)\n    c = step_three(b)\n    return other(c)\n',
        "rule_config": {'HC-OR003': {'min_run': 3}},
        "hd": None,
        "expected": [{'rule_id': 'HC-OR003', 'severity': 'warning', 'message': "Orchestrators 'flow_a' and 'flow_b' share 3 consecutive operations. Consider extracting the shared sequence as a pure helper (if side-effect-free) or as a chain (if I/O is involved). Orchestrators are not composable (HC-OR001); reusable orchestration logic belongs in helpers or chains.", 'source_location': 'case_HC-OR003.py:8:1', 'context': 'def flow_b(x):', 'fixable': False}],
    },
    {
        "id": 'HC-OR003-identical',
        "source": '@orchestrator\ndef flow_a(x):\n    a = step_one(x)\n    b = step_two(a)\n    c = step_three(b)\n    return c\n@orchestrator\ndef flow_b(x):\n    a = step_one(x)\n    b = step_two(a)\n    c = step_three(b)\n    return c\n',
        "rule_config": {'HC-OR003': {'min_run': 3}},
        "hd": None,
        "expected": [{'rule_id': 'HC-OR003', 'severity': 'warning', 'message': "Orchestrators 'flow_a' and 'flow_b' share 3 consecutive operations. Consider extracting the shared sequence as a pure helper (if side-effect-free) or as a chain (if I/O is involved). Orchestrators are not composable (HC-OR001); reusable orchestration logic belongs in helpers or chains.", 'source_location': 'case_HC-OR003-identical.py:8:1', 'context': 'def flow_b(x):', 'fixable': False}],
    },
    {
        "id": 'HC-OR003-disjoint',
        "source": '@orchestrator\ndef flow_a(x):\n    a = alpha(x)\n    b = beta(a)\n    return b\n@orchestrator\ndef flow_b(x):\n    c = gamma(x)\n    d = delta(c)\n    return d\n',
        "rule_config": {'HC-OR003': {'min_run': 1}},
        "hd": None,
        "expected": [],
    },
    {
        "id": 'HC002',
        "source": "from honest_type import chain, link, vocabulary\nA = vocabulary({'t1': {'a'}})\nB = vocabulary({'t2': {'b'}})\n@link(accepts=A, emits=A)\ndef s1(m):\n    return m\n@link(accepts=B, emits=B)\ndef s2(m):\n    return m\nc = chain(s1, s2)\n",
        "rule_config": {},
        "hd": None,
        "expected": [{'rule_id': 'HC002', 'severity': 'error', 'message': "Chain link 's2' accepts types the previous link does not emit: ['t2']. Change this link's accepts, change the previous link's emits, or insert a link between them that produces the types.", 'source_location': 'case_HC002.py:10:5', 'context': 'chain(s1, s2)', 'fixable': False}],
    },
    {
        "id": 'HC-P017',
        "source": 'def a():\n    return Response()\n',
        "rule_config": {},
        "hd": None,
        "expected": [{'rule_id': 'HC-P017', 'severity': 'error', 'message': "Function 'a' produces HTTP output without being a declared @link with an emits vocabulary. Declare emits covering status, content-type, body shape, headers, and cookies, or delegate to a declared serializer link.", 'source_location': 'case_HC-P017.py:1:1', 'context': 'def a():', 'fixable': False}],
    },
    {
        "id": 'HC004',
        "source": "from honest_type import vocabulary, binding, classify\nv = vocabulary({'t1': {'a'}, 't2': {'b'}})\nb = binding({'t1': 'slot1'})\nr = classify(tok, v, bind=b)\n",
        "rule_config": {},
        "hd": None,
        "expected": [{'rule_id': 'HC004', 'severity': 'warning', 'message': "Type 't2' is declared in the vocabulary but no binding slot or composed type uses it. Bind it to a slot, use it in a composed type, or remove it from the vocabulary.", 'source_location': 'case_HC004.py:2:5', 'context': "vocabulary({'t1': {'a'}, 't2': {'b'}})", 'fixable': False}],
    },
    {
        "id": 'HC005',
        "source": "from honest_type import vocabulary, binding, classify\nv = vocabulary({'t1': {'a'}})\nb = binding({'t1': 'slot1', 'tX': 'slotX'})\nr = classify(tok, v, bind=b)\n",
        "rule_config": {},
        "hd": None,
        "expected": [{'rule_id': 'HC005', 'severity': 'warning', 'message': "Binding references type 'tX' not found in the paired vocabulary, so no classified token can reach its slot. Add the type to the vocabulary, or remove the binding entry.", 'source_location': 'case_HC005.py:3:5', 'context': "binding({'t1': 'slot1', 'tX': 'slotX'})", 'fixable': False}],
    },
    {
        "id": 'HC010',
        "source": "from honest_type import link, vocabulary, binding\nacc = vocabulary({'t1': {'a'}})\nemt = vocabulary({'t2': {'b'}})\nbnd = binding({'t2': 'slot2'})\n@link(accepts=acc, emits=emt, binds=bnd)\ndef f(manifest):\n    return manifest\n",
        "rule_config": {},
        "hd": None,
        "expected": [{'rule_id': 'HC004', 'severity': 'warning', 'message': "Type 't1' is declared in the vocabulary but no binding slot or composed type uses it. Bind it to a slot, use it in a composed type, or remove it from the vocabulary.", 'source_location': 'case_HC010.py:2:7', 'context': "vocabulary({'t1': {'a'}})", 'fixable': False}, {'rule_id': 'HC010', 'severity': 'warning', 'message': "Link 'f' declares it emits ['t2'] but its body never produces them: it writes no manifest slot bound to the type and does not accept the type. Write the slot, drop the type from emits, or accept it.", 'source_location': 'case_HC010.py:6:1', 'context': 'def f(manifest):', 'fixable': False}],
    },
    {
        "id": 'HC-HF001',
        "source": "FEATURES = {'known': {'states': {'on', 'off'}}}\nx = feature_state(s, 'unknown')\n",
        "rule_config": {},
        "hd": None,
        "expected": [{'rule_id': 'HC-HF001', 'severity': 'error', 'message': "feature_state references 'unknown', which is not a declared flag in FEATURES.", 'source_location': 'case_HC-HF001.py:2:5', 'context': "feature_state(s, 'unknown')", 'fixable': False}],
    },
    {
        "id": 'HC-HF002',
        "source": "FEATURES = {'flag': {'states': {'on', 'off'}}}\nTABLE = {'on': 1}\nx = TABLE[feature_state(s, 'flag')]\n",
        "rule_config": {},
        "hd": None,
        "expected": [{'rule_id': 'HC-HF002', 'severity': 'warning', 'message': "Handler table 'TABLE' dispatched on feature 'flag' has no entry for state(s) ['off']; the flag entering that state raises KeyError. Add the missing entry, or handle the state.", 'source_location': 'case_HC-HF002.py:3:5', 'context': "TABLE[feature_state(s, 'flag')]", 'fixable': False}],
    },
    {
        "id": 'HC-SUP001',
        "source": '# honest: ignore HC-P003: no rule here\nx = 1\n',
        "rule_config": {},
        "hd": None,
        "expected": [{'rule_id': 'HC-SUP001', 'severity': 'error', 'message': 'Suppression directive suppressed nothing: no named rule fired in its scope. Remove the directive, or correct the rule it names.', 'source_location': 'case_HC-SUP001.py:1:1', 'context': '# honest: ignore HC-P003: no rule here', 'fixable': False}],
    },
    {
        "id": 'HC-SUP002',
        "source": '# honest: disable HC-P003\nclass A:\n    pass\n',
        "rule_config": {},
        "hd": None,
        "expected": [{'rule_id': 'HC-P003', 'severity': 'info', 'message': "Class 'A' has no declared base. Use a TypedDict for data shapes or a pure function.", 'source_location': 'case_HC-SUP002.py:2:1', 'context': 'class A:', 'fixable': False}, {'rule_id': 'HC-SUP002', 'severity': 'error', 'message': "Suppression directive carries no reason. Add ': <why the violation stands>' so the next reader can judge whether it still holds.", 'source_location': 'case_HC-SUP002.py:1:1', 'context': '# honest: disable HC-P003', 'fixable': False}],
    },
    {
        "id": 'HC-P004-door',
        "source": 'def save(path):\n    return open(path).read()\n',
        "rule_config": {},
        "hd": 'module m\n  boundary_in fn save : (path: str) -> str side_effect reads "filesystem"\n',
        "expected": [],
    },
    {
        "id": 'HC-P004-door-boundary-out',
        "source": 'def save(path):\n    return open(path).read()\n',
        "rule_config": {},
        "hd": 'module m\n  boundary_out fn save : (path: str) -> str side_effect reads "filesystem"\n',
        "expected": [],
    },
    {
        "id": 'HC-P004-door-reader',
        "source": 'def save(path):\n    return open(path).read()\n',
        "rule_config": {},
        "hd": 'module m\n  reader fn save : (path: str) -> str side_effect reads "filesystem"\n',
        "expected": [],
    },
    {
        "id": 'HC-SYN',
        "source": 'def f(:\n',
        "rule_config": {},
        "hd": None,
        "expected": [{'rule_id': 'HC-SYN', 'severity': 'error', 'message': 'case_HC-SYN.py does not parse under python: error at line 1, column 7', 'source_location': 'case_HC-SYN.py:1:7', 'context': '', 'fixable': False}],
    },
]


def _canon(diags):
    import json
    return sorted(json.dumps(d, sort_keys=True) for d in diags)


def _message_failures(check_source):
    bad = []
    for case in _MSG_CASES:
        declaration = _declaration_for(case["hd"])
        got = check_source(case["source"], f"case_{case['id']}.py", case["rule_config"], declaration)
        if _canon(got) != _canon(case["expected"]):
            bad.append(f"record pinning {case['id']!r}: got {_canon(got)}, expected {_canon(case['expected'])}")
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
    bad.extend(_st001_declaration_failures(check_source))
    bad.extend(_or003_failures(check_source))
    bad.extend(_message_failures(check_source))
    return bad
