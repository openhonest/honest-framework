# scenario: io_monitor records the link's I/O calls while leaving its result unchanged
# inherits: hd=python/honest-test/honest-test.hd::io_monitor -> feature=specs/features/honest-test.feature::io_monitor records the link's I/O calls while leaving its result unchanged
"""honest-test conformance: io_monitor records a link's I/O, then restores (§4.4).

io_monitor is the boundary-isolation plug injected into verify_under_monitor. It runs the
link while patching known I/O functions to record each call, then restores the originals
(changing no result). A link that opens a file yields a non-empty record; a link that does
no I/O yields an empty one. The second call proving empty also proves the restore worked —
the patch from the first call did not leak into it.

No classes, no mocks: the links are real functions, and io_monitor is the real record-and-
restore instrumentation, not a test double.
"""

import json
import subprocess
import sys

from honest_test import io_monitor


def _io_link(manifest):
    """Does I/O: opens a file and closes it."""
    with open(__file__):
        pass
    return manifest


def _stream_link(manifest):
    """Does I/O by writing straight to the stdout stream, bypassing print()."""
    sys.stdout.write("")
    return manifest


def _pure_link(manifest):
    """Does no I/O."""
    return {**manifest, "seen": True}


_INPUT_PROBE_SOURCE = r"""
import json
import sys
from honest_test import io_monitor

def stream_calls(manifest):
    manifest["line"] = input()
    manifest["remaining"] = sys.stdin.read()
    print("stdout through print")
    sys.stdout.write("stdout direct\n")
    sys.stderr.write("stderr direct\n")

manifest = {}
calls = io_monitor(stream_calls, manifest)
print(json.dumps({"calls": calls, "manifest": manifest}))
"""


def probe_io_monitor():
    bad = []

    recorded = io_monitor(_io_link, {"a": 1})
    if not any(name.split(".")[-1] == "open" for name in recorded):
        bad.append(f"io_monitor should record the open() call a link makes, got {recorded!r}")

    # The .hd names sys.stdout/stderr/stdin among io_monitor's patched targets, so a link that
    # writes straight to the stream — not through print() — must be detected too. This pins the
    # stream path that the open() case alone never exercises.
    streamed = io_monitor(_stream_link, {"a": 1})
    if not any(name.split(".")[-1] == "write" for name in streamed):
        bad.append(f"io_monitor should record a direct sys.stdout.write call, got {streamed!r}")

    child = subprocess.run(
        [sys.executable, "-c", _INPUT_PROBE_SOURCE],
        input="one\ntwo\n",
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    if child.returncode != 0:
        bad.append(f"io_monitor could not record the real stream calls: {child.stderr!r}")
    else:
        result = json.loads(child.stdout.splitlines()[-1])
        names = set(result["calls"])
        expected = {"print", "input", "stdout.write", "stderr.write", "stdin.read"}
        observed = {name.removeprefix("builtins.").removeprefix("sys.") for name in names}
        if observed != expected:
            bad.append(f"io_monitor stream call names: expected {sorted(expected)!r}, got {sorted(observed)!r}")
        if result["manifest"] != {"line": "one", "remaining": "two\n"}:
            bad.append(f"io_monitor changed the real stdin results: {result['manifest']!r}")
        if child.stdout.splitlines()[:-1] != ["stdout through print", "stdout direct"]:
            bad.append(f"io_monitor changed stdout: {child.stdout!r}")
        if child.stderr != "stderr direct\n":
            bad.append(f"io_monitor changed stderr: {child.stderr!r}")

    clean = io_monitor(_pure_link, {"a": 1})
    if clean != []:
        bad.append(f"io_monitor should record nothing for a link that does no I/O (and must have restored the patched functions), got {clean!r}")

    return bad


def run():
    messages = probe_io_monitor()
    for message in messages:
        print(f"FAIL probe_io_monitor: {message}")
    print(f"io_monitor: {'passed' if not messages else f'{len(messages)} failed'}")
    return 0 if not messages else 1


if __name__ == "__main__":
    raise SystemExit(run())
