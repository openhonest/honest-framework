"""honest-test conformance runner.

Discovers every conformance/probe_*.py fragment and runs each IN THIS PROCESS, then runs
the laws (laws_htest.run()). A probe is self-contained: it builds its cases as data, calls
the real honest_test function through its module-level `run()`, and returns the list of
failure strings (empty when every case holds). The runner imports each probe module and
calls that `run()` directly, so the honest_test under test is the one already imported here
— not a fresh copy in a child process.

Running in-process is what the mutation gate (mutate.py) depends on: it overrides one source
file in memory with a mutant and exec's this __main__, so the suite must exercise that
in-memory module. A subprocess would re-import the real module from disk and never see the
mutant, so every mutant would survive. The suite is run in one interpreter for the same
reason the whole framework's pytest run is: honest_test is pure, so one probe's imports do
not change what the next probe sees.

The runner reports one line per probe and exits non-zero if any probe, or the laws, did not
pass.

    uv run --package honest-test python honest-test/conformance/run_conformance.py
"""

import importlib
import sys
import traceback
from pathlib import Path

# ---- value-oracle fixtures (spec section 8.6) ----
# proof_run.value_function_map reads _VALUE_FUNCTIONS so the value gate can resolve the $ref/$call
# names a suite.json value_case uses: honest-test's own exported callables, plus the live fixtures a
# case needs (a pure link the honesty checks run, a state-machine builder, the honest-type
# constructors). Every fixture is a real callable, never a stand-in that fakes a result.
import honest_test as _ht
from honest_type import binding as _binding
from honest_type import ok as _ok
from honest_type import state_machine as _state_machine
from honest_type import transition as _transition
from honest_type import vocabulary as _vocabulary


def _double(x):
    return x * 2


def _parity(n):
    return {"ok": "even"} if n % 2 == 0 else {"err": {"code": "odd"}}


def _box(n):
    return {"n": n, "doubled": n * 2}


def _apply_fn(f, x):
    return f(x)


async def _add_async(a, b):
    return a + b


def _echo(value):
    return value


def _first_of(fns, x):
    return fns[0](x)


def _pure_link(manifest):
    return {**manifest, "seen": True}


def _make_machine():
    return _state_machine(
        {"locked", "unlocked"},
        {"coin", "push"},
        {("locked", "coin"): "unlocked", ("unlocked", "push"): "locked"},
        "locked",
    )


def _make_vocabulary(declarations):
    return _vocabulary({name: set(members) for name, members in declarations.items()})


def _emit_format(manifest):
    return _ok(manifest)


def _always_ok(manifest):
    return _ok(manifest)


_VALUE_FUNCTIONS = {
    "double": _double,
    "parity": _parity,
    "box": _box,
    "apply_fn": _apply_fn,
    "add_async": _add_async,
    "echo": _echo,
    "first_of": _first_of,
    "pure_link": _pure_link,
    "make_machine": _make_machine,
    "vocabulary": _make_vocabulary,
    "binding": _binding,
    "transition": _transition,
    "emit_format": _emit_format,
    "always_ok": _always_ok,
    **{name: getattr(_ht, name) for name in _ht.__all__ if callable(getattr(_ht, name))},
}


def probe_paths(here):
    """Every probe fragment in the conformance directory, in a stable order."""
    return sorted(here.glob("probe_*.py"))


def run_probe(path):
    """Import one probe module and call its `run()` in this process. Returns the list of
    failure strings the probe reported, or a one-item list when the probe's import or run
    raised (a crash is a failure, named, so one bad probe does not abort the batch)."""
    name = path.stem
    try:
        module = importlib.import_module(name)
        reported = module.run()
    except Exception:
        return [f"{name} raised:\n{traceback.format_exc()}"]
    return list(reported) if reported else []


def run(here):
    probes = probe_paths(here)
    if not probes:
        print("no probe_*.py fragments found", file=sys.stderr)
        return 2
    failures = []
    for path in probes:
        bad = run_probe(path)
        print(f"{'pass' if not bad else 'FAIL'}  {path.name}")
        if bad:
            failures.append((path.name, bad))
    print(f"\n{len(probes) - len(failures)}/{len(probes)} probes passed")
    for name, lines in failures:
        for line in lines:
            print(f"  {name}: {line}")
    return 1 if failures else 0


def main():
    here = Path(__file__).resolve().parent
    if str(here) not in sys.path:
        sys.path.insert(0, str(here))
    probe_status = run(here)
    laws_htest = importlib.import_module("laws_htest")
    laws_status = laws_htest.run()
    return probe_status or laws_status


if __name__ == "__main__":
    sys.exit(main())
