"""The filesystem-side reader (honest-check.hd: read_source, role reader).

It pulls one file's complete text from disk and hands it back as a string, so
an orchestrator can pass that text to check_source. It reads and does nothing
else: it does not parse, check, or write.

Per the declaration, path is always a concrete, recognized source file: file
discovery at the boundary keeps only files whose extension honest-parse
recognizes and drops anything an exclude glob matches, so a directory, a
nonexistent path, and an unrecognized extension are filtered out before this
reader runs. The spec states no fault for a path that becomes unreadable after
discovery, so this reader declares no absence case and names no missing-path
fault. There is no implicit default on the read: the full text comes back, and
an empty file returns the empty string.
"""


def read_source(path: str) -> str:
    """Return the full text of the one file at path; an empty file returns ""."""
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()
