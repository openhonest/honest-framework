"""Mutation-adequacy gate (honest-test section 9.6): the I/O harness around honest-test's pure engine.

For each module, mutate every source file one site at a time (honest_test.enumerate_mutants) and require
the module's conformance suite to fail on each mutant. A surviving mutant must be declared equivalent,
with a reason, in conformance/mutants_setaside.json, keyed by its file-qualified label; any undeclared
survivor fails the gate. mutation_adequacy reports caught + set_aside == total. Not linted (the boundary).

Each mutant is run IN-PROCESS and the mutants are fanned across the cores. The first design spawned one
Python subprocess per mutant; profiling showed 97% of every mutant's time was process spawn plus
re-importing the whole package, while the conformance work itself took ~4ms. Here a meta-path finder
overrides exactly one module's source with the mutant string — no file is written, so parallel workers
cannot collide — and the module's conformance __main__ is exec'd in-process. A per-mutant alarm bounds
non-terminating mutants (a removed loop increment): a timeout means the suite did not pass, so the mutant
is caught. Early-exit falls out of run_conformance's __main__, which stops at the failing half (suite or
laws) and raises SystemExit.
"""

import importlib.abc
import importlib.util
import io
import json
import multiprocessing as mp
import os
import signal
import subprocess
import sys
import time
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from honest_test import enumerate_mutants, mutation_adequacy

ROOT = Path(__file__).resolve().parent
# In-worker SIGALRM is the fast path for a Python-level non-terminating mutant; the parent's hard
# deadline is the backstop for one SIGALRM cannot reach (asyncio.run installs its own signal handling),
# where the parent SIGKILLs the whole worker. A legitimate mutant runs in well under 0.2s, so these are
# generous. They are kept tight on purpose: a mutant that shifts a size constant (honest-test's
# adversarial generators build strings up to ~1 MB) allocates for the whole window before the alarm
# fires, so a long timeout times that runaway by the worker count in resident memory. The run-to-run
# flap that tempted a longer window was warm-worker state leakage, fixed by the stdlib snapshot below,
# not by waiting longer.
_TIMEOUT_SECONDS = 2
_DEADLINE_SECONDS = 4

# Total resident memory ceiling for the whole run (parent + every worker). A legitimate conformance run
# peaks around 50 MB; a pathological mutant (a removed loop increment that grows a list, a size constant
# in honest-test's adversarial generators) can allocate without bound until the timeout fires. RLIMIT_AS
# is a no-op on macOS, so the parent instead polls each worker's RSS and SIGKILLs (then respawns) any that
# crosses the per-worker cap — a memory blowup is a detected behaviour change, caught exactly like a hang.
# The worker count is clamped so workers x cap stays under the ceiling with headroom for the parent and
# for the overshoot between polls.
_MEMORY_CEILING_BYTES = 6 * 1024**3
_PARENT_RESERVE_BYTES = 1536 * 1024**2  # parent process + OS slack + between-poll overshoot allowance
_WORKER_RSS_CAP_BYTES = 512 * 1024**2   # >> the ~50 MB a legitimate run needs, so no real survivor is killed
_MEMORY_POLL_SECONDS = 0.05
_WORKERS = max(1, min((os.cpu_count() or 2) - 1, (_MEMORY_CEILING_BYTES - _PARENT_RESERVE_BYTES) // _WORKER_RSS_CAP_BYTES))


class _MutantLoader(importlib.abc.SourceLoader):
    """A source loader that serves a mutant string in place of a file's real contents, so the module
    imports the mutated code while keeping its real filename (for __file__ and tracebacks)."""

    def __init__(self, path, source):
        self._path = path
        self._source = source.encode("utf-8")

    def get_filename(self, fullname):
        return self._path

    def get_data(self, path):
        return self._source


class _MutantFinder(importlib.abc.MetaPathFinder):
    """Overrides exactly one module's source (the mutated file); every other import defers to the normal
    machinery. Per-process state, so parallel workers never collide on a shared file."""

    def __init__(self):
        self.fqmn = None
        self.path = None
        self.source = None

    def find_spec(self, name, path=None, target=None):
        if name != self.fqmn:
            return None
        return importlib.util.spec_from_file_location(name, self.path, loader=_MutantLoader(self.path, self.source))


_FINDER = _MutantFinder()
_MODULE = None
_RUNNER_PATH = None
_RUNNER_CODE = None


def _init_worker(module):
    """Per-worker setup: install the finder once, put the conformance dir on the path (so `import laws_*`
    resolves), and compile the runner once."""
    global _MODULE, _RUNNER_PATH, _RUNNER_CODE
    _MODULE = module
    conf = ROOT / f"honest-{module}" / "conformance"
    _RUNNER_PATH = conf / "run_conformance.py"
    _RUNNER_CODE = compile(_RUNNER_PATH.read_text(encoding="utf-8"), str(_RUNNER_PATH), "exec")
    sys.meta_path.insert(0, _FINDER)
    sys.path.insert(0, str(conf))
    sys.argv = [str(_RUNNER_PATH)]


def _alarm(_signum, _frame):
    raise TimeoutError("mutant did not terminate")


def _purge():
    """Drop the package and its conformance modules from sys.modules so the next mutant re-imports them
    fresh (the mutated file via the finder, the rest from disk)."""
    for name in list(sys.modules):
        if name == f"honest_{_MODULE}" or name.startswith(f"honest_{_MODULE}.") or name.startswith("laws_"):
            del sys.modules[name]


# Stdlib modules a conformance harness patches at runtime (honest-test's non-determinism probe replaces
# attributes of these inside a call_monitor, restoring them in a finally). A mutant that breaks that
# restore would leave a module patched for every later mutant in the same warm worker — making a real
# survivor flap to "caught" depending on run order. Snapshotting and restoring these around each run
# isolates one mutant from the next without paying a fresh interpreter per mutant.
_PATCHABLE = ("asyncio", "getpass", "multiprocessing", "os", "platform", "random", "secrets", "threading", "time", "uuid")


def _snapshot_stdlib():
    return [(sys.modules[name], dict(sys.modules[name].__dict__)) for name in _PATCHABLE if name in sys.modules]


def _restore_stdlib(snapshot):
    for module, saved in snapshot:
        module.__dict__.clear()
        module.__dict__.update(saved)


def _suite_passes(fqmn, path, source):
    """True iff the conformance __main__ exits 0 with `path` overridden by `source`. A non-terminating
    mutant trips the alarm and counts as caught (returns False). Stdlib state is snapshotted and restored
    around the run so a mutant that leaks a patch cannot poison the next mutant in this warm worker."""
    _FINDER.fqmn, _FINDER.path, _FINDER.source = fqmn, path, source
    _purge()
    snapshot = _snapshot_stdlib()
    signal.signal(signal.SIGALRM, _alarm)
    signal.alarm(_TIMEOUT_SECONDS)
    try:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            exec(_RUNNER_CODE, {"__name__": "__main__", "__file__": str(_RUNNER_PATH)})
        return True  # ran to the end without SystemExit (no failure path taken)
    except SystemExit as exc:
        return (exc.code or 0) == 0
    except Exception:
        # The suite crashed on this mutant (or the alarm fired) — that is a detected behaviour change,
        # exactly as a non-zero subprocess exit was. Caught.
        return False
    finally:
        signal.alarm(0)
        _restore_stdlib(snapshot)
        _FINDER.fqmn = None


def _worker_main(module, task_conn, result_conn):
    """A warm worker: import once, then loop — receive a mutant, send back whether it survived. Runs
    until it receives the stop sentinel (or the parent kills it for blowing the deadline)."""
    _init_worker(module)
    while True:
        mutant = task_conn.recv()
        if mutant is None:
            return
        try:
            survived = _suite_passes(mutant["fqmn"], mutant["path"], mutant["source"])
        except BaseException:
            survived = False
        result_conn.send(survived)


class _Worker:
    """A killable warm worker process the parent dispatches one mutant at a time, so a mutant that hangs
    past the deadline can be SIGKILLed and replaced without losing the rest of the run."""

    def __init__(self, module):
        self._module = module
        self._spawn()

    def _spawn(self):
        self._task_recv, self._task_send = mp.Pipe(duplex=False)
        self._result_recv, self._result_send = mp.Pipe(duplex=False)
        self.proc = mp.Process(target=_worker_main, args=(self._module, self._task_recv, self._result_send), daemon=True)
        self.proc.start()
        self.current = None
        self.since = None

    def dispatch(self, mutant):
        self.current = mutant
        self.since = time.monotonic()
        self._task_send.send(mutant)

    def ready(self):
        return self.current is not None and self._result_recv.poll()

    def take(self):
        survived = self._result_recv.recv()
        mutant, self.current, self.since = self.current, None, None
        return mutant, survived

    def overdue(self):
        return self.since is not None and time.monotonic() - self.since > _DEADLINE_SECONDS

    def kill_and_respawn(self):
        """A mutant that no signal could stop — kill the worker and start a fresh one. The mutant it was
        running is caught (a program that does not halt is a detected behaviour change)."""
        mutant = self.current
        self.proc.kill()
        self.proc.join()
        self._spawn()
        return mutant

    def stop(self):
        try:
            self._task_send.send(None)
        except (BrokenPipeError, OSError):
            pass
        self.proc.join(timeout=2)
        if self.proc.is_alive():
            self.proc.kill()


def _rss_bytes(pids):
    """Resident memory in bytes for each pid, via one `ps` call (the RSS column is KB on macOS and
    Linux). A pid that has already exited is simply omitted. Used to cap a runaway worker."""
    if not pids:
        return {}
    listed = subprocess.run(["ps", "-o", "pid=,rss=", "-p", ",".join(str(pid) for pid in pids)], capture_output=True, text=True).stdout
    rss = {}
    for line in listed.splitlines():
        parts = line.split()
        if len(parts) == 2:
            rss[int(parts[0])] = int(parts[1]) * 1024
    return rss


def _fqmn(path, module):
    """The dotted module name for a source file, e.g. honest_type/boundary.py -> honest_type.boundary;
    a package __init__.py -> honest_type."""
    parts = path.relative_to(ROOT / f"honest-{module}" / "src").with_suffix("").parts
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)


def _src_files(module, only=None):
    files = sorted((ROOT / f"honest-{module}" / "src" / f"honest_{module}").rglob("*.py"))
    return [f for f in files if only is None or only in f.name]


def _set_aside(module):
    path = ROOT / f"honest-{module}" / "conformance" / "mutants_setaside.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _baseline_passes(module):
    """The conformance suite must pass on the UNMUTATED source before adequacy is meaningful (§9.6).
    A suite that is red for any other reason registers every mutant as caught — the line ran against a
    failing oracle — and reports false adequacy. Run the runner once on the real source first."""
    conf = ROOT / f"honest-{module}" / "conformance"
    result = subprocess.run(
        [sys.executable, str(conf / "run_conformance.py")],
        cwd=str(conf), capture_output=True, text=True,
    )
    return result.returncode == 0


def _mutants(module, only=None):
    """Every mutant of every source file, each tagged with the dotted module name and real path so a
    worker can override it in memory. `only` (a filename substring) narrows to one file for fast iteration."""
    mutants = []
    for path in _src_files(module, only):
        source = path.read_text(encoding="utf-8")
        relpath, fqmn = str(path.relative_to(ROOT)), _fqmn(path, module)
        for mutant in enumerate_mutants(source):
            mutants.append({"fqmn": fqmn, "path": str(path), "source": mutant["source"], "operator": mutant["operator"], "label": f"{relpath}:{mutant['label']}"})
    return mutants


def _run_module(module, only=None):
    """Fan the mutants across killable warm workers. Each worker runs one mutant at a time; a mutant that
    runs past the deadline (one no in-worker signal could stop) has its worker SIGKILLed and replaced,
    and is counted as caught. A surviving mutant is one whose worker reported the suite still passing.
    `only` (a filename substring) narrows mutation to one source file for fast iteration."""
    mutants = _mutants(module, only)
    pending = list(reversed(mutants))  # pop() from the end
    workers = [_Worker(module) for _ in range(min(_WORKERS, len(mutants) or 1))]
    survivors = []
    done = 0
    last_memory_poll = 0.0
    while done < len(mutants):
        for worker in workers:
            if worker.current is None and pending:
                worker.dispatch(pending.pop())
        progressed = False
        for worker in workers:
            if worker.ready():
                mutant, survived = worker.take()
                if survived:
                    survivors.append({"operator": mutant["operator"], "label": mutant["label"]})
                done += 1
                progressed = True
            elif worker.overdue():
                worker.kill_and_respawn()  # the hung mutant is caught; nothing to record
                done += 1
                progressed = True
        # Cap resident memory: a mutant whose run grows past the per-worker cap has its worker SIGKILLed
        # and replaced, and is counted as caught (a memory blowup is a detected behaviour change, like a
        # hang). Polled, not per-iteration, so the `ps` cost is bounded.
        now = time.monotonic()
        if now - last_memory_poll >= _MEMORY_POLL_SECONDS:
            last_memory_poll = now
            busy = [worker for worker in workers if worker.current is not None]
            rss = _rss_bytes([worker.proc.pid for worker in busy])
            for worker in busy:
                if rss.get(worker.proc.pid, 0) > _WORKER_RSS_CAP_BYTES:
                    worker.kill_and_respawn()
                    done += 1
                    progressed = True
        if not progressed:
            time.sleep(0.002)
    for worker in workers:
        worker.stop()
    return mutation_adequacy(mutants, survivors, _set_aside(module))


def main(modules):
    # Signal the conformance suite that it is running under mutation, so probes that drive a heavy
    # real external service (the PostgreSQL integration probe) skip themselves: mutation re-runs the
    # whole suite once per mutant, and a real server in that loop is prohibitively slow. Those probes
    # verify integration in a normal suite run; their pure logic is mutation-tested by pure probes.
    # Workers inherit this env, as does the baseline subprocess.
    os.environ["HONEST_MUTATION"] = "1"
    status = 0
    for module in modules:
        # `module:filename-substring` narrows mutation to matching source files for fast iteration.
        module, _, only = module.partition(":")
        if not _baseline_passes(module):
            print(f"mutate: honest-{module} — the conformance suite does not pass on the unmutated source; "
                  f"adequacy is undefined until it is green (fix the suite first).", file=sys.stderr)
            status = 1
            continue
        report = _run_module(module, only or None)
        print(f"mutate: honest-{module} — {report['caught']} caught, {report['set_aside']} set aside, {len(report['undeclared'])} undeclared of {report['total']} mutants")
        for survivor in report["undeclared"]:
            print(f"  SURVIVED  {survivor['operator']}  {survivor['label']}")
        if not report["adequate"]:
            status = 1
    if status == 0:
        print("mutate: every mutant is caught or declared equivalent — the suite is mutation-adequate.")
    else:
        print("mutate: undeclared survivors above — add a conformance case that catches each, or declare it equivalent with a reason in conformance/mutants_setaside.json.", file=sys.stderr)
    return status


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
