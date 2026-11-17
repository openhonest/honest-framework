#!/usr/bin/env python
"""`is_err` is the Fault recognizer's one input. This is what ends the arms that preceded it.

Adam reserved `is_err` on 2026-11-17, so the fault arm of a bare `value | Fault` union is told from
the value arm by a field name no other record may carry. Before that the recognizer keyed on
whatever the author had to hand, and eleven places in this framework still do, keying on five
different things: `code`, `problem`, `problem` and `remedy` together, `err`, and the removed
envelope. A success value that legitimately carries a currency `code` or an HTTP status `code` reads
as a failure to the first of those, and a migrated fault reads as a success to the rest.

honest-type's `is_fault` therefore accepts `is_err` or `code` for now. Dropping `code` in one step
would make every unmigrated fault unrecognizable, and the chain executor would hand a fault to the
next link as its manifest and keep running: silent failure, in the module built to prevent it. So
the old arm outlives the ruling for exactly as long as an unmigrated fault needs it, and a temporary
allowance with nothing to end it becomes permanent, which is how `edge` lasted eight months.

This script is the end. While a site still reads the old key it warns and names each one with its
file and the key it reads. On the run where the last one goes it fails instead, telling the reader to
delete the `code` arm of `is_fault`, and this script with it. The site list is written out below
rather than discovered, because the discriminating test is the very heuristic being removed: a scan
that guessed which dicts were faults would have to guess the thing in question. A hand-written list
cannot be satisfied by writing less, because removing a line from it shows up in the diff.

    uv run python python/fault-tag-check.py [tree ...]
"""

import pathlib
import sys

# Each site: the file, the text that proves it still reads a pre-tag key, and what it keys on.
SITES = (
    ("honest-type/src/honest_type/types.py", 'or "code" in value', "code; the transitional arm of is_fault itself"),
    ("honest-test/src/honest_test/oracle.py", '"problem" in resolved', "problem"),
    ("honest-test/src/honest_test/io_boundary.py", '"problem" in value', "problem"),
    ("honest-test/conformance/probe_run_suite.py", '"problem" in value and "remedy" in value', "problem and remedy"),
    ("honest-test/conformance/probe_parse_source.py", '"problem" in value and "remedy" in value', "problem and remedy"),
    ("honest-test/conformance/probe_run_cli.py", '"problem" in value and "remedy" in value', "problem and remedy"),
    ("honest-test/conformance/probe_compare_output.py", '"err" in result', "err; the removed envelope"),
    ("honest-test/conformance/probe_run_case.py", '"err" in result', "err; the removed envelope"),
    ("honest-test/conformance/probe_evaluate_case.py", '"err" in result', "err; the removed envelope"),
    ("honest-errors/conformance/run_conformance.py", '"code" in value', "code"),
    ("honest-utilities/src/honest_utilities/__init__.py", '"code" in value', "code"),
)

DEFAULT_TREES = (pathlib.Path(__file__).resolve().parent,)


class FaultTagMigrated(Exception):
    """Raised when no site reads a pre-tag key any more, so the transitional arm can go.

    `is_err` is the recognizer's one input, but honest-type's `is_fault` still accepts `code`,
    because deleting that arm while an unmigrated fault exists would turn a fault into the next
    link's manifest and let the chain run on. The allowance is deliberate and it is temporary. This
    is the thing that makes it temporary: while a site remains the check warns and names it, and on
    the run where the last one goes it raises, naming what to delete.
    """


def survivors(tree):
    """The sites that still read a pre-tag key, as (file, key) pairs, and the files not found.

    A missing file is reported rather than counted as migrated. A site whose file was renamed has
    not been migrated, and reading absence as success is how a check congratulates itself.
    """
    found, missing = [], []
    for relative, probe, keyed_on in SITES:
        path = tree / relative
        if not path.is_file():
            missing.append(relative)
        elif probe in path.read_text(encoding="utf-8"):
            found.append((relative, keyed_on))
    return found, missing


def fault_tag_migration(found):
    """Warn while any site reads a pre-tag key; raise once none does."""
    if not found:
        raise FaultTagMigrated(
            "No site reads a pre-tag key any more, so delete the transitional arm: in "
            "honest-type/src/honest_type/types.py, is_fault reads `\"is_err\" in value or \"code\" in "
            "value`, and the `or \"code\" in value` goes, along with the paragraph of its docstring "
            "that explains it. Then delete this script, which exists only to reach this moment. It "
            "reads the sites it was handed, so confirm it was handed the whole tree before acting"
        )
    lines = [f"  {relative} reads {keyed_on}" for relative, keyed_on in found]
    return (f"{len(found)} of {len(SITES)} site(s) still recognize a fault by a pre-tag key, so "
            "honest-type's is_fault keeps accepting `code` and a success value carrying a currency "
            "or status code can still read as a failure:\n" + "\n".join(lines) +
            "\nEach one becomes `\"is_err\" in value`, against honest-type's recognizer rather than "
            "its own copy. This warning becomes an exception on the run where the last one goes")


def main(argv: list) -> int:
    trees = [pathlib.Path(a) for a in argv[1:]] or list(DEFAULT_TREES)
    absent = [t for t in trees if not t.is_dir()]
    for tree in absent:
        print(f"fault-tag-check: no such tree: {tree}", file=sys.stderr)
    if absent:
        return 2
    found, missing = [], []
    for tree in trees:
        tree_found, tree_missing = survivors(tree)
        found.extend(tree_found)
        missing.extend(tree_missing)
    for relative in missing:
        print(f"fault-tag-check: site not found, so it was not judged: {relative}", file=sys.stderr)
    if len(missing) == len(SITES) * len(trees):
        print("fault-tag-check: no site was found under any named tree, so nothing was judged. "
              "A check that reads nothing must not report the migration done.", file=sys.stderr)
        return 2
    try:
        print(f"fault-tag-check: {fault_tag_migration(found)}", file=sys.stderr)
    except FaultTagMigrated as migrated:
        print(f"fault-tag-check: {migrated}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
