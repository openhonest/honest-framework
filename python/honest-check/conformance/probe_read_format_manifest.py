"""Honest probe for honest-check's read_format_manifest (feature Scenario: read_format_manifest).

read_format_manifest returns the NOTHING absence arm (None) for an empty path,
standing HC-REF004 down; for a configured path it reads honest-format's
manifest.json and returns the FormatVocabulary it carries (each enumerated hf-*
attribute mapped to its closed list of values, a dict<str, list<str>>). The spec
states no fault for a configured path that cannot be read or does not parse, so it
answers NOTHING there too.

The empty-path and the two read-failure cases pin the NOTHING arm (None). The
configured-path case writes a real manifest.json and demands the FormatVocabulary
back, so a `return None` stub (which would pass every NOTHING case) fails here.
The on-disk manifest.json layout is honest-format's and is not pinned by this
module's spec or .hd (no honest-format module exists in-repo yet); this probe
takes the FormatVocabulary (dict<str, list<str>>) to be the manifest's content
serialized directly, which the GAPS block records.
"""
import json
import os
import tempfile

# A FormatVocabulary: each enumerated hf-* attribute mapped to its closed value list.
_VOCAB = {"hf-format": ["currency", "percent"], "hf-type": ["text", "number"]}


def probe_read_format_manifest():
    """read_format_manifest answers NOTHING for no/unreadable manifest and the vocabulary for a real one."""
    try:
        from honest_check import read_format_manifest
    except ImportError as exc:
        return [f"cannot import read_format_manifest: {exc}"]

    bad = []

    # Empty path: the NOTHING absence arm (None), standing HC-REF004 down.
    got = read_format_manifest(path="")
    if got is not None:
        bad.append(f"read_format_manifest('') -> {got!r}, expected None (NOTHING)")

    # Configured path: the FormatVocabulary the manifest.json carries.
    fd, path = tempfile.mkstemp(suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(_VOCAB, handle)
        got = read_format_manifest(path=path)
    finally:
        os.unlink(path)
    if got != _VOCAB:
        bad.append(f"read_format_manifest(manifest) -> {got!r}, expected {_VOCAB!r}")

    # Configured but unparsable: no fault, answers NOTHING (None).
    fd, path = tempfile.mkstemp(suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write("{ not valid json")
        got = read_format_manifest(path=path)
    finally:
        os.unlink(path)
    if got is not None:
        bad.append(f"read_format_manifest(unparsable) -> {got!r}, expected None (NOTHING)")

    # Configured but missing: no fault, answers NOTHING (None).
    missing = os.path.join(tempfile.gettempdir(), "no_such_manifest_probe_xyz.json")
    if os.path.exists(missing):
        os.unlink(missing)
    got = read_format_manifest(path=missing)
    if got is not None:
        bad.append(f"read_format_manifest(missing) -> {got!r}, expected None (NOTHING)")

    return bad
