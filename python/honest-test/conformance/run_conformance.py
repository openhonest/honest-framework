"""honest-test conformance runner.

Discovers every conformance/probe_*.py fragment and runs each as its own process. A
probe is self-contained: it builds its cases as data, calls the real honest_test
function, and exits 0 when every case holds, non-zero when any fails (or when the
honest_test module it imports is still absent, which is the current clean-slate red).
Running each probe in its own process keeps one probe's import state from reaching the
next, and matches how a probe runs on its own.

The runner reports one line per probe and exits non-zero if any probe did not pass.

    uv run --package honest-test python honest-test/conformance/run_conformance.py
"""

import subprocess
import sys
from pathlib import Path


def probe_paths(here):
    """Every probe fragment in the conformance directory, in a stable order."""
    return sorted(here.glob("probe_*.py"))


def run_probe(interpreter, path):
    """Run one probe in its own process and return its exit code and output."""
    done = subprocess.run(
        [interpreter, str(path)],
        capture_output=True,
        text=True,
    )
    return done.returncode, done.stdout, done.stderr


def last_line(stdout, stderr):
    """The most telling line of a failed probe's output: its last stderr line, or its
    last stdout line when stderr is empty."""
    text = stderr.strip() or stdout.strip()
    lines = text.splitlines()
    return lines[-1] if lines else "(no output)"


def run(here, interpreter):
    probes = probe_paths(here)
    if not probes:
        print("no probe_*.py fragments found", file=sys.stderr)
        return 2
    failures = []
    for path in probes:
        code, out, err = run_probe(interpreter, path)
        print(f"{'pass' if code == 0 else 'FAIL'}  {path.name}")
        if code != 0:
            failures.append((path.name, last_line(out, err)))
    print(f"\n{len(probes) - len(failures)}/{len(probes)} probes passed")
    for name, tail in failures:
        print(f"  {name}: {tail}")
    return 1 if failures else 0


def main():
    here = Path(__file__).resolve().parent
    return run(here, sys.executable)


if __name__ == "__main__":
    sys.exit(main())
