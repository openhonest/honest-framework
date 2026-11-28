# bootstrap-exempt: standalone gate test for Honest Test §9.6; the mutation runner is bootstrap tooling.
"""Check that each warm-worker verdict uses its own selected source."""

import os
import signal
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

_PYTHON_ROOT = Path(__file__).resolve().parents[2]
_PROBE = """from honest_reload_fixture.result import ok


def check():
    return int(ok({"name": "fresh"}) != {"ok": {"name": "fresh"}})
"""
_ORIGINAL = 'def ok(manifest):\n    return {"ok": manifest}\n'
_CHANGED = 'def ok(manifest):\n    return {"wrong": manifest}\n'
_RUNS = {
    "baseline-first": [
        ("baseline", "original", "survived"),
        ("mutant", "changed", "caught"),
        ("restored", "original", "survived"),
    ],
    "mutant-first": [
        ("fresh mutant", "changed", "caught"),
        ("restored", "original", "survived"),
    ],
}
_PROBE_NAMES = ("probe_warm_reload", "fragments.warm_reload")


def check_worker(probe_name, order):
    """Run the real worker in this process against a temporary conformance suite."""
    sys.path.insert(0, str(_PYTHON_ROOT))
    import mutate

    sources = {"original": _ORIGINAL, "changed": _CHANGED}
    with TemporaryDirectory() as temp:
        mutate.ROOT = Path(temp)
        packages = mutate.ROOT / "src"
        package = packages / "honest_reload_fixture"
        package.mkdir(parents=True)
        (package / "__init__.py").touch()
        path = package / "result.py"
        path.write_text(_ORIGINAL, encoding="utf-8")
        sys.path.insert(0, str(packages))

        conformance = mutate.ROOT / "honest-reload_fixture/conformance"
        conformance.mkdir(parents=True)
        output = conformance.joinpath(*probe_name.split(".")).with_suffix(".py")
        output.parent.mkdir(exist_ok=True)
        output.write_text(_PROBE, encoding="utf-8")
        (conformance / "run_conformance.py").write_text(
            f"from {probe_name} import check\n\nraise SystemExit(check())\n", encoding="utf-8"
        )
        mutate._init_worker("reload_fixture")

        failures = []
        for stage, source, expected in _RUNS[order]:
            observed, reason = mutate._suite_verdict("honest_reload_fixture.result", str(path), sources[source])
            if observed != expected:
                failures.append(f"{stage}: expected {expected}, got {observed} ({reason})")

    for failure in failures:
        print(f"FAIL {probe_name} ({order}): {failure}")
    return int(bool(failures))


def check_resource_fixtures():
    """Retain the standalone resource holders in the Persist suite."""
    sys.path.insert(0, str(_PYTHON_ROOT))
    import mutate

    names = ("postgres_fixture", "turso_fixture")
    path = _PYTHON_ROOT / "honest-persist/src/honest_persist/__init__.py"
    source = path.read_text(encoding="utf-8")
    with TemporaryDirectory() as temp:
        mutate.ROOT = Path(temp)
        conformance = mutate.ROOT / "honest-persist/conformance"
        conformance.mkdir(parents=True)
        for name in names:
            (conformance / f"{name}.py").write_text("RESOURCE = object()\n", encoding="utf-8")
        imports = "".join(f"from {name} import RESOURCE as {name}_resource\n" for name in names)
        (conformance / "run_conformance.py").write_text(imports, encoding="utf-8")
        mutate._init_worker("persist")

        first = mutate._suite_verdict("honest_persist", str(path), source)
        original = {name: sys.modules[name].RESOURCE for name in names if name in sys.modules}
        second = mutate._suite_verdict("honest_persist", str(path), source)
        if (first, second) != (("survived", None), ("survived", None)):
            print(f"FAIL Persist resource runner: {first!r}, {second!r}")
            return 1
        for name in names:
            if name not in original or sys.modules[name].RESOURCE is not original[name]:
                print(f"FAIL Persist resource runner: {name} was reloaded")
                return 1
    return 0


def check_signal_restoration():
    """A warm worker preserves process signals between two unchanged suites."""
    sys.path.insert(0, str(_PYTHON_ROOT))
    import mutate

    with TemporaryDirectory() as directory:
        mutate.ROOT = Path(directory)
        conformance = mutate.ROOT / "honest-reload_fixture" / "conformance"
        conformance.mkdir(parents=True)
        (conformance / "run_conformance.py").write_text(
            "import signal\n"
            "for number in (signal.SIGTERM, signal.SIGINT):\n"
            "    if signal.getsignal(number) != signal.SIG_DFL:\n"
            "        raise SystemExit(1)\n"
            "    signal.signal(number, lambda number, frame: None)\n",
            encoding="utf-8",
        )
        for number in (signal.SIGTERM, signal.SIGINT):
            signal.signal(number, signal.SIG_DFL)
        mutate._init_worker("reload_fixture")
        verdicts = [
            mutate._suite_verdict("honest_reload_fixture", str(conformance / "unused.py"), "")
            for _ in range(2)
        ]
    if verdicts != [("survived", None), ("survived", None)]:
        print(f"FAIL mutation worker allowed signal handlers to leak: {verdicts!r}")
        return 1
    return 0


def check_worker_workspace():
    """The parent reclaims its fixture workspace after a killed worker."""
    sys.path.insert(0, str(_PYTHON_ROOT))
    import mutate

    worker = mutate._Worker("persist")
    workspace = worker._postgres_root
    try:
        (workspace / "fixture").write_text("temporary PostgreSQL workspace\n", encoding="utf-8")
        worker.proc.kill()
    finally:
        worker.stop()
    if workspace.exists() or worker.proc.exitcode != -9:
        print(f"FAIL mutation worker retained the PostgreSQL workspace: {workspace}")
        return 1
    return 0


def check_completed_failure():
    """Replay a reported failure before a later probe can obscure the verdict."""
    runner = Path(__file__).with_name("run_conformance.py")
    with TemporaryDirectory() as directory:
        root = Path(directory)
        entry = root / runner.name
        entry.write_bytes(runner.read_bytes())
        (root / "probe_first.py").write_text("def run(): return 1\n")
        (root / "probe_second.py").write_text("def run(): print('second probe ran'); return 0\n")
        for mode, expected_second_probe in (("0", True), ("1", False)):
            run = subprocess.run(
                [sys.executable, str(entry)],
                env={**os.environ, "HONEST_MUTATION": mode},
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            observed_second_probe = "second probe ran" in run.stdout
            if run.returncode != 1 or observed_second_probe != expected_second_probe or run.stderr:
                print(f"FAIL conformance failure propagation in mode {mode}: {run!r}")
                return 1
    return 0


def check_identity_mutant_skipped():
    """A mutant whose replacement text equals its original text changes nothing, so it can never be
    killed and must never be scheduled (Honest Test §9.6): scheduling it reports a false survivor. An
    empty-string literal "" yields a constant_replace ""->"", the identity case this guards. The gate
    generates every mutant of a one-constant fixture and asserts none reproduces the original source."""
    sys.path.insert(0, str(_PYTHON_ROOT))
    import mutate

    with TemporaryDirectory() as temp:
        mutate.ROOT = Path(temp)
        package = mutate.ROOT / "honest-idfix" / "src" / "honest_idfix"
        package.mkdir(parents=True)
        source = 'def f():\n    value = ""\n    return value\n'
        (package / "__init__.py").write_text(source, encoding="utf-8")
        mutants, _unspliced = mutate._mutants("idfix")
        identity = [m for m in mutants if m["source"] == source]
        if identity:
            print(f"FAIL identity mutant scheduled (replacement == original): {[m['label'] for m in identity]}")
            return 1
    return 0


def run():
    """Isolate each probe layout and start order in a fresh worker process."""
    failed = bool(check_completed_failure())
    failed |= bool(check_identity_mutant_skipped())
    for probe_name in _PROBE_NAMES:
        for order in _RUNS:
            result = subprocess.run([sys.executable, __file__, probe_name, order], timeout=45, check=False)
            failed |= result.returncode != 0
    for case in ("fixtures", "fixture-cleanup", "signal-restoration"):
        result = subprocess.run([sys.executable, __file__, case], timeout=45, check=False)
        failed |= result.returncode != 0
    if not failed:
        print("PASS mutation worker: probe and fragment imports reload; Persist resource fixtures stay cached")
    return int(failed)


if __name__ == "__main__":
    args = sys.argv[1:]
    if args == ["fixtures"]:
        raise SystemExit(check_resource_fixtures())
    if args == ["fixture-cleanup"]:
        raise SystemExit(check_worker_workspace())
    if args == ["signal-restoration"]:
        raise SystemExit(check_signal_restoration())
    raise SystemExit(check_worker(*args) if args else run())
