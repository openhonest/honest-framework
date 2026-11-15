"""Honest probe for honest-check's run_check (feature Scenarios: run_check).

run_check is the CLI orchestrator. Three scenarios fix its two modes and the
crossing-mode read failure:

  - base mode (CliArgs.declaration empty): discover the files, run check_source
    per file (plus the whole-program passes), prepare the report, and return the
    ExitCode resolve_exit_code decides.
  - crossing mode (declaration names an .hd that reads): cross it against the
    package and return the ExitCode from the same tail.
  - crossing-mode read failure (declaration names a missing / unparseable .hd):
    read_declaration answers a raw reason, run_check assembles honest-check's
    Fault through read_fault and routes that Fault outward as its ExitCode | Fault
    answer (the door later discharges it as exit 2).

This is a near-integration probe over a REAL temp tree, not mocks. In base mode a
clean tree returns ExitCode '0' (nothing blocks) and a tree holding a bare `if`
returns ExitCode '1' (HC-P001, an error at the default Declared adoption, survives
to drive exit 1). The read-failure case passes --declaration at a path that does
not exist and demands a Fault back (a record carrying problem and remedy), not an
ExitCode string.

Two more cases force base-mode .hd discovery (bead honest-framework-n64). A reader
that does I/O (open) under a module .hd that marks it a reader returns ExitCode '0':
run_check must find the file's nearest module .hd and pass the Declaration to
check_source so HC-P004 is dropped on the declared door. The same source in a tree
with no module .hd returns '1', because the declaration is NOTHING and the finding
stands. The pair pins that the discovery, not a blanket drop, stands the finding
down.

A stub returning '0' always passes the clean case and the .hd-discovery case but
fails the `if` case, the no-.hd mirror (both expect '1') and the read-failure case
(expects a Fault), so the probe is not vacuous.

GAPS: (1) the bare-`if` -> HC-P001 -> error -> exit 1 chain rests on the rule
catalogue and the adoption table (sections 4.2, 9.4), not the run_check scenario.
(2) ExitCode is the vocabulary member '0'/'1' (a string); this probe normalises
with str() so an int-coded exit would still match, because the string-vs-int
encoding is not fixed by the scenario. (3) that HC-P004 is the rule a reader's I/O
trips, and that a reader is the role whose door drops it, rests on the rule
catalogue and the boundary-rule drop (section 3.4), not the run_check scenario.
"""
import tempfile
from pathlib import Path

_CLEAN = "def choose(flag):\n    return 1\n"
_BAD_IF = "def choose(flag):\n    if flag:\n        return 1\n    return 0\n"

# A module .hd declaring `load` a reader (a door), so HC-P004's I/O-in-the-interior
# finding is dropped on it (check_source re-checks a flagged non-boundary function
# against the discovered declaration, section 3.4 / §HC-P004).
_READER_HD = (
    "module honest-foo\n\n  layer correctness\n\n"
    '  reader fn load : (path: str) -> bytes side_effect reads "file" note "reads a file"\n'
)
# The reader's source: `load` does I/O (open) with no decorator, so the decorator
# check alone would flag HC-P004; only the .hd marking it a reader stands it down.
_READER_SRC = "def load(path):\n    open('data.txt')\n"


def _field(fault, name):
    """Read one Fault field whether it is a dict or a record."""
    if isinstance(fault, dict):
        return fault.get(name)
    return getattr(fault, name, None)


def probe_run_check():
    """run_check returns ExitCode '0' on a clean tree, '1' on a violation, and a Fault on a missing --declaration."""
    try:
        from honest_check import run_check
    except ImportError as exc:
        return [f"cannot import run_check: {exc}"]

    bad = []

    # Base mode, clean tree -> ExitCode '0'.
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "clean.py").write_text(_CLEAN)
        got = run_check([d])
        if str(got) != "0":
            bad.append(f"run_check([clean tree]) -> {got!r}, expected ExitCode '0'")

    # Base mode, tree with a bare `if` -> ExitCode '1'.
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "bad.py").write_text(_BAD_IF)
        got = run_check([d])
        if str(got) != "1":
            bad.append(f"run_check([tree with `if`]) -> {got!r}, expected ExitCode '1'")

    # Base mode, .hd discovery: a reader that does I/O under a module .hd that
    # marks it a door -> HC-P004 dropped -> ExitCode '0'. run_check must find the
    # file's nearest module .hd (honest-foo/honest-foo.hd) and pass the Declaration
    # to check_source so the boundary rule stands down (bead honest-framework-n64).
    with tempfile.TemporaryDirectory() as d:
        mod = Path(d) / "honest-foo"
        mod.mkdir()
        (mod / "honest-foo.hd").write_text(_READER_HD)
        (mod / "io.py").write_text(_READER_SRC)
        got = run_check([str(mod)])
        if str(got) != "0":
            bad.append(
                f"run_check([tree with module .hd marking load a reader]) -> {got!r}, "
                f"expected ExitCode '0' (HC-P004 dropped on the declared door)"
            )

    # Base mode, mirror: the same reader source in a tree with NO module .hd ->
    # the declaration is NOTHING, the decorator verdict stands -> HC-P004 fires ->
    # ExitCode '1'. This pins that the discovery, not a blanket drop, is what
    # stands the finding down.
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "io.py").write_text(_READER_SRC)
        got = run_check([d])
        if str(got) != "1":
            bad.append(
                f"run_check([same reader source, no module .hd]) -> {got!r}, "
                f"expected ExitCode '1' (HC-P004 fires with no declaration)"
            )

    # Crossing-mode read failure: --declaration names a missing .hd -> Fault.
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "clean.py").write_text(_CLEAN)
        missing = str(Path(d) / "nope.hd")
        got = run_check([d, "--declaration", missing])
        if isinstance(got, str):
            bad.append(
                f"run_check([tree, --declaration <missing>]) -> ExitCode {got!r}, "
                f"expected a Fault carrying problem and remedy"
            )
        elif _field(got, "problem") is None or _field(got, "remedy") is None:
            bad.append(
                f"run_check([tree, --declaration <missing>]) -> {got!r}, "
                f"expected a Fault carrying both problem and remedy"
            )

    return bad
