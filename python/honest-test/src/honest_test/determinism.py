"""Non-determinism detection (section 4.5): a non-boundary link must not touch a non-deterministic source.

honest-check catches non-determinism statically from the AST; honest-test traps it at RUNTIME, which is
stricter — it catches a source reached through an attribute chain or dynamic dispatch that slips past
static analysis. call_monitor patches the watch-list symbols so any call to one is recorded;
verify_determinism runs the link under the monitor and, for a non-boundary link, warns about every
source it touched.

The watch list is the patchable, module-level callable subset of honest-check's HC008
NONDETERMINISTIC_WATCH_LIST: every concrete callable that list names is trapped here, and the conformance
probe checks the two against each other directly (honest-test traps nothing honest-check omits, and every
module-level callable honest-check publishes is trapped), so the lists cannot drift. honest-check's
entries the runtime monitor cannot patch — attribute reads (os.environ, sys.argv), C-type-bound methods
(datetime.datetime.now), and the id builtin — stay honest-check's static responsibility; its module-glob
entries (random.*, secrets.*, platform.*) are trapped representatively. A symbol absent on the running
platform (e.g. os.uname off POSIX) is skipped rather than failing the monitor. The decision
(nondeterminism_finding) and the list are pure; the monitor and the link run are the boundary — this file
mutates module attributes and executes the link under instrumentation, exactly the impurity the linter
forbids in business logic, so HC-P004/HC-P011 are disabled here.
"""


import asyncio
import contextlib
import getpass
import multiprocessing
import os
import platform
import random
import secrets
import threading
import time
import uuid

from honest_test.honesty import _finding, _is_boundary, _name

_MODULES = {
    "asyncio": asyncio,
    "getpass": getpass,
    "multiprocessing": multiprocessing,
    "os": os,
    "platform": platform,
    "random": random,
    "secrets": secrets,
    "threading": threading,
    "time": time,
    "uuid": uuid,
}

# The non-deterministic sources a non-boundary link must not call: every module-level callable in honest-
# check's HC008 list (randomness, time, process and thread state), plus a representative member of each of
# its module-glob entries. Verified against the published list by the conformance probe, so the two stay
# in lockstep.
_WATCH_LIST = (
    "uuid.uuid1",
    "uuid.uuid3",
    "uuid.uuid4",
    "uuid.uuid5",
    "os.urandom",
    "os.getenv",
    "os.getlogin",
    "os.getpid",
    "os.getppid",
    "os.getcwd",
    "os.uname",
    "time.time",
    "time.time_ns",
    "time.monotonic",
    "time.perf_counter",
    "time.process_time",
    "time.sleep",
    "getpass.getpass",
    "getpass.getuser",
    "threading.current_thread",
    "threading.get_ident",
    "threading.active_count",
    "multiprocessing.current_process",
    "multiprocessing.cpu_count",
    "asyncio.get_event_loop",
    "asyncio.current_task",
    "random.random",
    "random.randint",
    "secrets.token_bytes",
    "platform.system",
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
        original = getattr(module, attr, None)
        if original is None:
            continue
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
