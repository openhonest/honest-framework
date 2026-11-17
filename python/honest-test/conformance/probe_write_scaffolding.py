"""honest-test conformance: write_scaffolding, the scaffolding sink.

write_scaffolding writes one do-not-edit scaffolding file into the configured
scaffolding directory and does nothing else, making no decision because the source
is already produced (.hd write_scaffolding note; feature "write_scaffolding writes
one do-not-edit scaffolding file"). Its one observable effect is the written file,
so this probe writes to a temp path and reads it back.

No classes, no mocks. The path and source are real; the function called is the real
honest_test.write_scaffolding; the effect is read back from the real filesystem.
"""

import os
import tempfile

from honest_test import write_scaffolding


def probe_write_scaffolding():
    """The file written at the given path holds exactly the source text handed in —
    byte for byte — because the sink writes what it is given and transforms nothing."""
    bad = []

    source = "def register(registry):\n    return registry\n"

    with tempfile.TemporaryDirectory() as directory:
        path = os.path.join(directory, "steps_format_pipeline.py")
        write_scaffolding(path, source)

        if not os.path.exists(path):
            bad.append(f"write_scaffolding should write the file at {path}")
            return bad
        with open(path) as handle:
            written = handle.read()
        if written != source:
            bad.append(f"the written file should hold the source exactly, got {written!r}")

    return bad


def run():
    messages = probe_write_scaffolding()
    for message in messages:
        print(f"FAIL probe_write_scaffolding: {message}")
    print(f"probe_write_scaffolding: {'PASS' if not messages else str(len(messages)) + ' failed'}")
    return 0 if not messages else 1


if __name__ == "__main__":
    raise SystemExit(run())
