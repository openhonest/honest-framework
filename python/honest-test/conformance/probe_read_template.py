"""RED probe for honest-test.read_template — the template reader (.hd, sections 8.2, 8.4, 8.6).

read_template reads one shipped step-library template file's complete text and
hands it back as a string, doing nothing else — it does not generate, resolve or
write. The probe points it at a real temporary file standing in for a shipped
template, then deletes the file. honest-test has no code yet, so importing
honest_test fails — the correct red state.
"""

import os
import tempfile

from honest_test import read_template


def probe_read_template():
    """read_template returns the full text of the template file at the given path,
    exactly as written, and transforms nothing."""
    bad = []

    template = (
        "# auto-generated scaffolding — do not edit\n"
        "def register(registry):\n"
        '    return registry.bind("given a response", _given_response)\n'
    )
    handle, path = tempfile.mkstemp(suffix=".py")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as f:
            f.write(template)

        got = read_template(path)
        if not isinstance(got, str):
            bad.append(f"read_template returned {type(got).__name__}, expected a str")
        elif got != template:
            bad.append(f"read_template returned {got!r}, expected the template's exact text {template!r}")
    finally:
        os.unlink(path)

    return bad


def run():
    failures = probe_read_template()
    for message in failures:
        print(f"FAIL read_template: {message}")
    print(f"read_template probe: {'PASS' if not failures else str(len(failures)) + ' failed'}")
    return failures


if __name__ == "__main__":
    raise SystemExit(1 if run() else 0)
