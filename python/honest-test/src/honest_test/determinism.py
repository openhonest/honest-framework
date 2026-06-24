"""Non-determinism detection (section 4.5): a non-boundary link must not touch a non-deterministic source.

honest-check catches non-determinism statically from the AST; honest-test traps it at RUNTIME, which is
stricter — it catches a source reached through an attribute chain or dynamic dispatch that slips past
static analysis. call_monitor patches the watch-list symbols so any call to one is recorded;
verify_determinism runs the link under the monitor and, for a non-boundary link, warns about every
source it touched.

The watch list mirrors honest-check's HC008 NONDETERMINISTIC_WATCH_LIST — the call-form, patchable
subset the runtime monitor can trap. The attribute-read and C-type-method entries honest-check carries
(os.environ, sys.argv, datetime.datetime.now) cannot be monkeypatched, so they stay honest-check's
static responsibility. The decision (nondeterminism_finding) and the list are pure; the monitor and the
link run are the boundary — this file mutates module attributes and executes the link under
instrumentation, exactly the impurity the linter forbids in business logic, so HC-P004/HC-P011 are
disabled here.
"""

# honest: disable HC-P004, HC-P011

import contextlib
import os
import random
import threading
import time
import uuid

from honest_test.honesty import _finding, _is_boundary, _name

_MODULES = {"os": os, "random": random, "threading": threading, "time": time, "uuid": uuid}

# The non-deterministic sources a non-boundary link must not call. Each is a no-argument-callable module
# function the monitor patches; the set mirrors the call-form, patchable entries of honest-check's HC008
# list (randomness, time, process state, thread identity).
_WATCH_LIST = (
    "random.random",
    "uuid.uuid1",
    "uuid.uuid4",
    "os.getpid",
    "os.getppid",
    "os.getcwd",
    "time.time",
    "time.time_ns",
    "time.monotonic",
    "time.perf_counter",
    "time.process_time",
    "threading.get_ident",
)


def nondeterministic_watch_list():
    """The non-deterministic sources a non-boundary link must not call (section 4.5), mirroring honest-
    check's HC008 list — the call-form subset the runtime monitor traps. Pure."""
    return list(_WATCH_LIST)


def nondeterminism_finding(link_name, boundary, detected):
    """The section 4.5 decision: a non-boundary link that called any non-deterministic source is a
    warning naming the sources; a boundary link, or one that touched none, is honest. Pure."""
    if detected and not boundary:
        called = sorted(set(detected))
        return _finding("nondeterminism_detected", link_name, f"Link called {called}; non-deterministic calls belong at boundaries")
    return None


def _recorder(path, original, detected):
    """A patched stand-in for a watched symbol: record that the source was called, then delegate to the
    original so the link still runs."""
    def wrapper(*args, **kwargs):
        detected.append(path)
        return original(*args, **kwargs)
    return wrapper


@contextlib.contextmanager
def call_monitor(watch_list):
    """Patch every watch-list symbol so a call to it is recorded, yielding the list of paths called
    (section 4.5). Every original is restored on exit, so the patch never outlives the monitored run.
    I/O: it mutates module attributes."""
    detected = []
    saved = []
    for path in watch_list:
        module_name, attr = path.rsplit(".", 1)
        module = _MODULES[module_name]
        original = getattr(module, attr)
        saved.append((module, attr, original))
        setattr(module, attr, _recorder(path, original, detected))
    try:
        yield detected
    finally:
        for module, attr, original in saved:
            setattr(module, attr, original)


def verify_determinism(link, manifest):
    """Run a link under the call monitor and flag a non-boundary link that touched a non-deterministic
    source (section 4.5). Returns a finding or None. I/O: it executes the link under instrumentation."""
    with call_monitor(_WATCH_LIST) as detected:
        link(manifest)
    return nondeterminism_finding(_name(link), _is_boundary(link), detected)
