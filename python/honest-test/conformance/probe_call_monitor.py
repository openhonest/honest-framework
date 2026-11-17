"""honest-test conformance: call_monitor records a link's non-deterministic calls (§4.5).

call_monitor is the nondeterminism plug injected into verify_under_monitor. It runs the link
while patching the trapped non-deterministic call-forms (time, random, uuid, os.urandom) to
record each call, then restores them (changing no result). A link that calls time.time()
yields a non-empty record; a deterministic link yields an empty one. The second call proving
empty also proves the restore worked.

No classes, no mocks: the links are real functions and call_monitor is the real record-and-
restore instrumentation.
"""

import time

from honest_test import call_monitor


def _nd_link(manifest):
    """Reads the clock — a non-deterministic call."""
    time.time()
    return manifest


def _pure_link(manifest):
    """Makes no non-deterministic call."""
    return {**manifest, "seen": True}


def probe_call_monitor():
    bad = []

    recorded = call_monitor(_nd_link, {"a": 1})
    if not recorded:
        bad.append(f"call_monitor should record the time.time() call a link makes, got {recorded!r}")

    clean = call_monitor(_pure_link, {"a": 1})
    if clean != []:
        bad.append(f"call_monitor should record nothing for a deterministic link (and must have restored the patched symbols), got {clean!r}")

    return bad


def run():
    messages = probe_call_monitor()
    for message in messages:
        print(f"FAIL probe_call_monitor: {message}")
    print(f"call_monitor: {'passed' if not messages else f'{len(messages)} failed'}")
    return 0 if not messages else 1


if __name__ == "__main__":
    raise SystemExit(run())
