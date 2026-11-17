"""honest-test conformance: run_suite, the CLI orchestrator.

run_suite drives the whole run over a source directory and returns a RunReport,
or passes a Fault outward when the module source does not parse for mutation
(.hd run_suite note; feature "run_suite drives the whole CLI run"). This probe
drives it over two tiny real temp source directories it creates — one trivial and
parseable, one that does not parse — and checks the shape of what comes back.

No classes, no mocks. The subject modules are real files written to a temp dir;
the function called is the real honest_test.run_suite. honest-test's own Fault is
a dict carrying "problem" and "remedy" (.hd type Fault), recognized by that shape.
"""

import os
import tempfile
from pathlib import Path

from honest_test import run_suite

_FIXTURES = Path(__file__).parent / "fixtures"


def _is_fault(value):
    return isinstance(value, dict) and "problem" in value and "remedy" in value


_RUNREPORT_FIELDS = (
    "chains",
    "links",
    "vocabularies",
    "permutations",
    "failures",
    "adversarial_rejected",
    "coverage",
    "mutation_caught",
    "mutation_total",
)

_COUNT_FIELDS = (
    "chains",
    "links",
    "vocabularies",
    "permutations",
    "failures",
    "adversarial_rejected",
    "mutation_caught",
    "mutation_total",
)


def _run_in(src_dir):
    """Call run_suite from a throwaway working directory so any coverage.json or
    scaffolding the run writes lands in temp space, not the project tree."""
    with tempfile.TemporaryDirectory() as work:
        start = os.getcwd()
        os.chdir(work)
        try:
            return run_suite(src_dir)
        finally:
            os.chdir(start)


def probe_run_suite():
    """A trivial parseable source directory runs to a RunReport carrying the nine
    declared fields with integer counts and a CoverageReport; a source directory
    whose module does not parse comes back as a Fault passed outward, never raised."""
    bad = []

    with tempfile.TemporaryDirectory() as src_dir:
        with open(os.path.join(src_dir, "trivial.py"), "w") as handle:
            handle.write('GREETING = "hi"\n')
        report = _run_in(src_dir)

        if _is_fault(report):
            bad.append(f"a trivial parseable source dir should run, got fault {report}")
        elif not isinstance(report, dict):
            bad.append(f"run_suite should return a RunReport dict, got {report!r}")
        else:
            for field in _RUNREPORT_FIELDS:
                if field not in report:
                    bad.append(f"RunReport is missing field {field!r}: {report}")
            for field in _COUNT_FIELDS:
                if field in report and not isinstance(report[field], int):
                    bad.append(f"RunReport.{field} should be an int, got {report.get(field)!r}")
            coverage = report.get("coverage")
            if not isinstance(coverage, dict) or "version" not in coverage:
                bad.append(f"RunReport.coverage should be a CoverageReport dict with a version: {coverage!r}")

    with tempfile.TemporaryDirectory() as src_dir:
        with open(os.path.join(src_dir, "broken.py"), "w") as handle:
            handle.write("def (:=!! @#$%\n")
        result = _run_in(src_dir)

        if not _is_fault(result):
            bad.append(f"a source that does not parse should come back as a Fault passed outward, got {result!r}")
        else:
            if not result.get("problem"):
                bad.append(f"the Fault should state the problem in a sentence: {result}")
            if not result.get("remedy"):
                bad.append(f"the Fault should state the remedy: {result}")

    # run_suite must actually run the honesty checks over the links it discovers, not
    # report a blanket 0. Two example adopter surfaces prove it: the honest one has no
    # dishonest link and must report 0 failures; the dishonest one mutates its manifest
    # and must report at least one.
    honest = _run_in(str(_FIXTURES / "adopter_honest"))
    if _is_fault(honest):
        bad.append(f"the honest adopter should run to a report, got fault {honest}")
    elif not isinstance(honest, dict):
        bad.append(f"the honest adopter should run to a RunReport, got {honest!r}")
    else:
        if honest.get("links", 0) < 1:
            bad.append(f"run_suite should discover the honest adopter's links, found {honest.get('links')!r}")
        if honest.get("failures") != 0:
            bad.append(f"the honest adopter has no dishonest link, so failures should be 0, got {honest.get('failures')!r}")

    dishonest = _run_in(str(_FIXTURES / "adopter_dishonest"))
    if _is_fault(dishonest):
        bad.append(f"the dishonest adopter should run to a report, got fault {dishonest}")
    elif not isinstance(dishonest, dict):
        bad.append(f"the dishonest adopter should run to a RunReport, got {dishonest!r}")
    elif dishonest.get("failures", 0) < 1:
        bad.append(
            "run_suite must run the honesty checks: the dishonest adopter mutates its "
            f"manifest, so failures should be >= 1, got {dishonest.get('failures')!r}"
        )

    # A boundary link and a link with no vocabulary are both skipped, so this adopter runs
    # to a report with zero failures and does not crash. Its boundary link even mutates its
    # manifest: running honesty over it would wrongly fault it, and enumerate_sets(None)
    # would raise — the skip guard is what this pins.
    boundary = _run_in(str(_FIXTURES / "adopter_boundary"))
    if _is_fault(boundary):
        bad.append(f"the boundary adopter should run to a report, got fault {boundary}")
    elif not isinstance(boundary, dict):
        bad.append(f"the boundary adopter should run to a RunReport, got {boundary!r}")
    else:
        if boundary.get("links", 0) < 2:
            bad.append(f"run_suite should discover both of the boundary adopter's links, found {boundary.get('links')!r}")
        if boundary.get("failures") != 0:
            bad.append(
                "a boundary link and a vocabulary-less link are both skipped, so failures "
                f"should be 0, got {boundary.get('failures')!r}"
            )

    # run_suite must discover chains and drive the chain-contract check (§4.6) over them.
    # The honest chain's join holds, so it reports 0 failures; the dishonest chain's
    # downstream link rejects a valid upstream output with a server fault, so it reports
    # at least one.
    chain_ok = _run_in(str(_FIXTURES / "adopter_chain_honest"))
    if _is_fault(chain_ok):
        bad.append(f"the honest-chain adopter should run to a report, got fault {chain_ok}")
    elif not isinstance(chain_ok, dict):
        bad.append(f"the honest-chain adopter should run to a RunReport, got {chain_ok!r}")
    else:
        if chain_ok.get("chains", 0) < 1:
            bad.append(f"run_suite should discover the honest adopter's chain, found {chain_ok.get('chains')!r}")
        if chain_ok.get("failures") != 0:
            bad.append(f"the honest chain's join holds, so failures should be 0, got {chain_ok.get('failures')!r}")

    chain_broken = _run_in(str(_FIXTURES / "adopter_chain_dishonest"))
    if _is_fault(chain_broken):
        bad.append(f"the dishonest-chain adopter should run to a report, got fault {chain_broken}")
    elif not isinstance(chain_broken, dict):
        bad.append(f"the dishonest-chain adopter should run to a RunReport, got {chain_broken!r}")
    else:
        if chain_broken.get("chains", 0) < 1:
            bad.append(f"run_suite should discover the dishonest adopter's chain, found {chain_broken.get('chains')!r}")
        if chain_broken.get("failures", 0) < 1:
            bad.append(
                "run_suite must drive the chain-contract check: the dishonest chain's "
                f"downstream link rejects a valid output with a server fault, so failures should be >= 1, got {chain_broken.get('failures')!r}"
            )

    # A chain whose upstream link declares no vocabulary cannot be contract-checked: it is
    # discovered but skipped, so run_suite runs to a report with zero failures and does not
    # crash on enumerate_test_cases(None).
    chain_untyped = _run_in(str(_FIXTURES / "adopter_chain_untyped"))
    if _is_fault(chain_untyped):
        bad.append(f"the untyped-chain adopter should run to a report, got fault {chain_untyped}")
    elif not isinstance(chain_untyped, dict):
        bad.append(f"the untyped-chain adopter should run to a RunReport, got {chain_untyped!r}")
    else:
        if chain_untyped.get("chains", 0) < 1:
            bad.append(f"run_suite should discover the untyped adopter's chain, found {chain_untyped.get('chains')!r}")
        if chain_untyped.get("failures") != 0:
            bad.append(f"a chain with no upstream vocabulary is skipped, so failures should be 0, got {chain_untyped.get('failures')!r}")

    # run_suite must discover state machines and drive the §5 checks over them. A valid
    # machine driven with honest-type's correct transition cannot fail, so the observable
    # is the adversarial-rejection count: every adversarial neighbor of a state or event
    # is correctly rejected, so adversarial_rejected is non-zero and failures stays 0.
    machine = _run_in(str(_FIXTURES / "adopter_machine"))
    if _is_fault(machine):
        bad.append(f"the machine adopter should run to a report, got fault {machine}")
    elif not isinstance(machine, dict):
        bad.append(f"the machine adopter should run to a RunReport, got {machine!r}")
    else:
        if machine.get("failures") != 0:
            bad.append(f"a valid machine cannot fail the state-machine checks, so failures should be 0, got {machine.get('failures')!r}")
        if machine.get("adversarial_rejected", 0) < 1:
            bad.append(
                "run_suite must drive the state-machine checks: a valid machine's adversarial "
                f"neighbors are all rejected, so adversarial_rejected should be > 0, got {machine.get('adversarial_rejected')!r}"
            )

    return bad


def run():
    messages = probe_run_suite()
    for message in messages:
        print(f"FAIL probe_run_suite: {message}")
    print(f"probe_run_suite: {'PASS' if not messages else str(len(messages)) + ' failed'}")
    return 0 if not messages else 1


if __name__ == "__main__":
    raise SystemExit(run())
