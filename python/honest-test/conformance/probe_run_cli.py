"""Conformance fragment for the run_cli scenario (honest-test.feature ~line 5).

Scenario: run_cli the CLI door hands src_dir to the orchestrator and returns its answer
  Then it hands src_dir to run_suite, which drives the whole run, and opens no file itself
  And it returns the assembled RunReport run_suite returned on a completed run
  And it returns the Fault run_suite passed outward when the module source could not
      be parsed for mutation
  And it raises nothing: a run that could not complete comes back as a Fault for the
      host to discharge as a non-zero exit

run_cli is a boundary that delegates to run_suite over a real source directory. We test
the REAL effect: we build a tiny temp source directory on disk and call the real
honest_test.run_cli on it. No mock, no stand-in — the whole point of a door is the
effect it produces, so we give it a real tree and read back what it returns.

run_cli's whole contract is the RunReport-vs-Fault distinction and that it raises
nothing. So each case drives one outcome and the probe asserts the SHAPE of the
returned record (RunReport keys, or Fault's problem/remedy), never over-pinning the
internal counts the whole pipeline produces.

This is its own fragment file so the other scenarios' fragments never collide with it.
run_conformance.py / laws_htest.py are untouched.
"""

import tempfile
from pathlib import Path

from honest_test import run_cli

# The nine fields a RunReport carries (honest-test.hd, type RunReport).
_RUNREPORT_FIELDS = {
    "chains",
    "links",
    "vocabularies",
    "permutations",
    "failures",
    "adversarial_rejected",
    "coverage",
    "mutation_caught",
    "mutation_total",
}

# A module with one length-bounded recognizer predicate, so the source-text path has a
# predicate to find and parse. Parseable Python.
_PARSEABLE_MODULE = (
    "def is_short(s: str) -> bool:\n"
    "    return len(s) <= 3\n"
)

# A module tree-sitter cannot parse into usable source: a broken def header. This is the
# unparseable-source case that makes mutate_source answer a Fault, which run_suite passes
# outward and run_cli returns.
_UNPARSEABLE_MODULE = (
    "def is_short(s: str -> bool:\n"
    "    return len(s) <= =\n"
)

_CASES = [
    {
        "name": "a valid source dir yields a RunReport",
        "module_text": _PARSEABLE_MODULE,
        "expect": "runreport",
    },
    {
        "name": "an unparseable source module yields a Fault, not a raise",
        "module_text": _UNPARSEABLE_MODULE,
        "expect": "fault",
    },
]


def _build_src_dir(root: Path, module_text: str) -> str:
    """Write one module under root/src/ and return root as the src_dir argument.

    The spec scans `src/` under the given directory (§11); the layout contract does not
    pin whether src_dir is the directory holding src/ or src/ itself, so this probe
    writes the module under src/ and names that gap in its report.
    """
    src = root / "src"
    src.mkdir(parents=True, exist_ok=True)
    (src / "mymodule.py").write_text(module_text)
    return str(root)


def _is_fault(got) -> bool:
    return isinstance(got, dict) and "problem" in got and "remedy" in got


def _is_runreport(got) -> bool:
    return (
        isinstance(got, dict)
        and _RUNREPORT_FIELDS <= set(got.keys())
        and "problem" not in got
        and "remedy" not in got
    )


def probe_run_cli():
    """run_cli hands src_dir to run_suite and returns its answer: a RunReport on a completed run, or the Fault run_suite passed outward on unparseable source, raising nothing."""
    bad = []
    for case in _CASES:
        with tempfile.TemporaryDirectory() as tmp:
            src_dir = _build_src_dir(Path(tmp), case["module_text"])
            try:
                got = run_cli(src_dir=src_dir)
            except Exception as exc:  # noqa: BLE001 — run_cli must raise nothing.
                bad.append(
                    f"run_cli({case['name']}) raised {type(exc).__name__}: {exc}; "
                    f"a run that could not complete must come back as a Fault, not a raise"
                )
                continue

            if case["expect"] == "runreport" and not _is_runreport(got):
                bad.append(
                    f"run_cli({case['name']}) -> {got!r}, expected a RunReport dict "
                    f"carrying {sorted(_RUNREPORT_FIELDS)} and no problem/remedy keys"
                )
            elif case["expect"] == "fault" and not _is_fault(got):
                bad.append(
                    f"run_cli({case['name']}) -> {got!r}, expected a Fault dict "
                    f"carrying 'problem' and 'remedy'"
                )
    return bad


def run():
    bad = probe_run_cli()
    for line in bad:
        print(line)
    print(f"probe_run_cli: {len(bad)} failure(s)")
    return bad


if __name__ == "__main__":
    import sys

    sys.exit(1 if run() else 0)
