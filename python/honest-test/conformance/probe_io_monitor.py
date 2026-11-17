"""honest-test conformance: io_monitor records a link's I/O, then restores (§4.4).

io_monitor is the boundary-isolation plug injected into verify_under_monitor. It runs the
link while patching known I/O functions to record each call, then restores the originals
(changing no result). A link that opens a file yields a non-empty record; a link that does
no I/O yields an empty one. The second call proving empty also proves the restore worked —
the patch from the first call did not leak into it.

No classes, no mocks: the links are real functions, and io_monitor is the real record-and-
restore instrumentation, not a test double.
"""

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


def probe_io_monitor():
    bad = []

    recorded = io_monitor(_io_link, {"a": 1})
    if not recorded:
        bad.append(f"io_monitor should record the open() call a link makes, got {recorded!r}")

    # The .hd names sys.stdout/stderr/stdin among io_monitor's patched targets, so a link that
    # writes straight to the stream — not through print() — must be detected too. This pins the
    # stream path that the open() case alone never exercises.
    streamed = io_monitor(_stream_link, {"a": 1})
    if not streamed:
        bad.append(f"io_monitor should record a direct sys.stdout.write call, got {streamed!r}")

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
