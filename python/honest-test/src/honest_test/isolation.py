"""Boundary isolation (section 4.4): a non-boundary link must not perform I/O.

honest-check catches I/O statically from the AST; honest-test traps it at RUNTIME, which is stricter —
it catches I/O reached through an attribute chain or dynamic dispatch that slips past static analysis.
io_monitor patches the watch-list symbols so a call is RECORDED but the I/O is NOT performed (section
4.4: detect without executing), so the isolation test never touches the real filesystem, process, or
network. verify_boundary_isolation runs the link under the monitor and, for a non-boundary link, warns
about every I/O it attempted — a link faulting after a blocked call still attempted it, so the run is
caught and the finding rests on what was detected.

The watch list is the patchable, module-level callable subset of honest-check's HC008 IO_WATCH_LIST:
the stdlib call-form entries the runtime monitor can patch. honest-check's third-party driver entries
(psycopg, requests) stay its static responsibility, exactly as the determinism monitor defers what it
cannot patch. The decision (io_finding) and the list are pure; the monitor and the link run are the
boundary — this file mutates module attributes and runs the link under instrumentation, the impurity the
linter forbids in business logic, so HC-P004/HC-P011/HC-P002 are disabled here.
"""

# honest: disable HC-P002: the isolation runner turns a raised exception into a reported outcome, which is what a boundary is for

import contextlib
import importlib

from honest_test.honesty import _finding, _is_boundary, _name

# The I/O sources a non-boundary link must not call: the stdlib call-form subset of honest-check's HC008
# IO_WATCH_LIST — filesystem, process/shell, and socket entry points the runtime monitor can patch. Every
# entry is an always-present stdlib callable, so the monitor resolves each without a presence guard.
_WATCH_LIST = (
    "builtins.open",
    "os.system",
    "os.popen",
    "os.remove",
    "os.rename",
    "os.mkdir",
    "os.rmdir",
    "os.listdir",
    "subprocess.run",
    "subprocess.Popen",
    "subprocess.call",
    "subprocess.check_output",
    "socket.socket",
    "shutil.copy",
    "shutil.move",
    "shutil.rmtree",
)


def io_watch_list():
    """The I/O sources a non-boundary link must not call (section 4.4), mirroring honest-check's HC008
    IO_WATCH_LIST — the call-form subset the runtime monitor traps. Pure."""
    return list(_WATCH_LIST)


def io_finding(link_name, boundary, detected):
    """The section 4.4 decision: a non-boundary link that performed any I/O is a warning naming the
    sources; a boundary link, or one that touched none, is honest. Pure."""
    if detected and not boundary:
        called = sorted(set(detected))
        return _finding("io_detected", link_name, f"Link performed I/O {called}; I/O belongs at boundaries. Add boundary=True if intentional.")
    return None


def _recorder(path, detected):
    """A patched stand-in for a watched I/O symbol: record that the call was made and return None
    WITHOUT performing the I/O (section 4.4: detect without executing)."""
    def wrapper(*args, **kwargs):
        detected.append(path)
        return None
    return wrapper


@contextlib.contextmanager
def io_monitor():
    """Patch every I/O watch-list symbol so a call is recorded but not performed (section 4.4), yielding
    the paths called. Every original is restored on exit, so the patch never outlives the monitored run.
    I/O: it mutates module attributes."""
    detected = []
    saved = []
    for path in _WATCH_LIST:
        module_name, attr = path.rsplit(".", 1)
        module = importlib.import_module(module_name)
        saved.append((module, attr, getattr(module, attr)))
        setattr(module, attr, _recorder(path, detected))
    try:
        yield detected
    finally:
        for module, attr, original in saved:
            setattr(module, attr, original)


def verify_boundary_isolation(link, manifest):
    """Run a link under the I/O monitor and flag a non-boundary link that performed I/O (section 4.4).
    A link that faults after a blocked I/O still attempted it, so the run is caught and the finding rests
    on what was detected. Returns a finding or None. I/O: it runs the link under instrumentation."""
    with io_monitor() as detected:
        try:
            link(manifest)
        except Exception:
            pass
    return io_finding(_name(link), _is_boundary(link), detected)
