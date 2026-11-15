"""Honest probe for honest-check's check_paths (feature Scenario: check_paths).

check_paths is the startup orchestrator: for each concrete source file it reads
the bytes, builds the CheckContext, and runs check_source over it (declaration
NOTHING), folding every file's diagnostics into one list, then resolves the
blocking threshold from severity and returns a StartupFindings carrying the full
folded list (all) and the blocking subset (blocking).

This is a near-integration probe over a REAL temp source tree, not a unit over
mocks: each case writes real .py files at real paths and calls the real
check_paths. check_paths runs check_source (the whole RuleId catalogue, per the
scenario), so a file holding a bare `if` fires HC-P001 — honest-check's "any if"
rule — which this probe demands appears in .all and, since HC-P001 is error
severity, in the error-threshold blocking subset. A tree of only clean files is
the absence case: both .all and .blocking are empty.

A stub returning StartupFindings(all=[], blocking=[]) passes the clean case but
fails the violation case (HC-P001 absent), so the probe is not vacuous.

GAP: the scenario fixes that a violation lands in .all and that blocking is the
severity-filtered subset, but it does NOT fix that a bare `if` maps to HC-P001 at
error severity — that mapping is owned by the rule catalogue (section 4.2 / the
conformance suite), not the check_paths scenario. See the probe report.
"""
import tempfile
from pathlib import Path

_CLEAN = "def choose(flag):\n    return 1\n"
_BAD_IF = "def choose(flag):\n    if flag:\n        return 1\n    return 0\n"


def _field(findings, name):
    """Read one StartupFindings field whether it is a dict or a record."""
    if isinstance(findings, dict):
        return findings.get(name)
    return getattr(findings, name, None)


def _rule_ids(diagnostics):
    """The rule_id of each diagnostic, dict or record."""
    out = []
    for d in diagnostics:
        if isinstance(d, dict):
            out.append(d.get("rule_id"))
        else:
            out.append(getattr(d, "rule_id", None))
    return out


def probe_check_paths():
    """check_paths folds every file's findings into StartupFindings.all and the severity-filtered subset into .blocking."""
    try:
        from honest_check import check_paths
    except ImportError as exc:
        return [f"cannot import check_paths: {exc}"]

    bad = []

    # Absence case: a tree of only clean files produces empty findings.
    with tempfile.TemporaryDirectory() as d:
        clean = Path(d) / "clean.py"
        clean.write_text(_CLEAN)
        findings = check_paths([str(clean)], "error")
        all_ = _field(findings, "all")
        blocking = _field(findings, "blocking")
        if not isinstance(all_, list):
            bad.append(f"check_paths([clean]) -> .all is {all_!r}, expected a list")
        elif all_:
            bad.append(
                f"check_paths([clean]).all -> {_rule_ids(all_)}, "
                f"expected [] (a clean file has no findings)"
            )
        if isinstance(blocking, list) and blocking:
            bad.append(
                f"check_paths([clean]).blocking -> {_rule_ids(blocking)}, "
                f"expected [] (nothing blocks on a clean file)"
            )

    # Violation case: a clean file plus a file with a bare `if`. HC-P001 lands in
    # .all; under severity 'error' the HC-P001 error also lands in .blocking.
    with tempfile.TemporaryDirectory() as d:
        clean = Path(d) / "clean.py"
        clean.write_text(_CLEAN)
        bad_file = Path(d) / "bad.py"
        bad_file.write_text(_BAD_IF)
        findings = check_paths([str(clean), str(bad_file)], "error")
        all_ = _field(findings, "all")
        blocking = _field(findings, "blocking")
        if not isinstance(all_, list):
            bad.append(f"check_paths([clean, if]) -> .all is {all_!r}, expected a list")
            all_ids = []
        else:
            all_ids = _rule_ids(all_)
            if "HC-P001" not in all_ids:
                bad.append(
                    f"check_paths([clean, if]).all -> {all_ids}, "
                    f"expected to contain HC-P001 for the bare `if`"
                )
        if not isinstance(blocking, list):
            bad.append(f"check_paths([clean, if]) -> .blocking is {blocking!r}, expected a list")
        else:
            blocking_ids = _rule_ids(blocking)
            if "HC-P001" not in blocking_ids:
                bad.append(
                    f"check_paths([clean, if]).blocking -> {blocking_ids}, "
                    f"expected to contain HC-P001 (error) under severity 'error'"
                )
            for rid in blocking_ids:
                if rid not in all_ids:
                    bad.append(
                        f"check_paths([clean, if]).blocking carries {rid!r} "
                        f"absent from .all {all_ids} — blocking must be a subset of all"
                    )

    return bad
