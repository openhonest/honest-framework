"""Conformance fragment for the read_config scenario (honest-test.feature ~line 40).

Scenario: read_config reads honest-test.toml and decodes it to the parsed table.
  Then it reads honest-test.toml and returns the plain decoded table, the
  predicates section as a map, and nothing more.
  And decoding the standard TOML format is part of the read; it builds no module
  record and resolves no values, because a door does not transform its input
  (honest-check HC-R006).
  And the table is empty when no honest-test.toml exists or it declares no
  predicates.

read_config is a reader (boundary), so this probe tests the real decode: it writes
a real temp .toml file, calls the real honest_test.read_config on its path, and
asserts the returned dict equals what tomllib produces (the plain parsed table).
The returned table must still carry the TOML section structure (a plain map of
maps), NOT a resolved SuppliedConfig — resolution is resolve_supplied_config's job.

Cases are data; one pure probe feeds them to the real function and returns a list
of failure strings, empty when every case holds. No classes, no mocks. This is its
own fragment file so the other scenarios' fragments never collide with it.
"""

import tempfile
import tomllib
from pathlib import Path

from honest_test import read_config

# A small TOML with a [predicates.<name>] table and keys. The expected value is
# exactly what tomllib.loads produces — the plain nested map, written out below as
# a literal so a stub returning {} cannot pass.
_TOML_TEXT = """\
[predicates.is_email]
valid = ["a@b.com", "c@d.org"]
invalid = ["nope", ""]
strategy = "supplied_only"

[predicates.in_range]
strategy = "fibonacci"
limit = 1000
negative = false
"""

# The raw decoded table, the plain map of maps the door returns. This is the
# section structure preserved, not a SuppliedConfig record.
_EXPECTED_TABLE = {
    "predicates": {
        "is_email": {
            "valid": ["a@b.com", "c@d.org"],
            "invalid": ["nope", ""],
            "strategy": "supplied_only",
        },
        "in_range": {
            "strategy": "fibonacci",
            "limit": 1000,
            "negative": False,
        },
    },
}


def probe_read_config():
    """read_config decodes honest-test.toml to the plain parsed table (a map of maps), builds no record, and returns the empty table when no file exists."""
    bad = []

    with tempfile.TemporaryDirectory() as tmp:
        # Case (a): a real TOML file with a table and keys. read_config must return
        # the plain decoded table, equal to what tomllib would produce.
        toml_path = Path(tmp) / "honest-test.toml"
        toml_path.write_text(_TOML_TEXT, encoding="utf-8")

        got = read_config(str(toml_path))

        oracle = tomllib.loads(_TOML_TEXT)  # a separate decoder, not the function under test
        if got != oracle:
            bad.append(
                f"read_config({str(toml_path)!r}) -> {got!r}, "
                f"expected the tomllib-decoded table {oracle!r}"
            )
        if got != _EXPECTED_TABLE:
            bad.append(
                f"read_config({str(toml_path)!r}) -> {got!r}, "
                f"expected the raw map of maps {_EXPECTED_TABLE!r} "
                f"(the section structure preserved, not a SuppliedConfig)"
            )

        # Case (b): no honest-test.toml exists at the path. The .hd note and the
        # scenario both say the table is empty when no file exists -> {}.
        missing_path = Path(tmp) / "does-not-exist.toml"
        got_missing = read_config(str(missing_path))
        if got_missing != {}:
            bad.append(
                f"read_config({str(missing_path)!r}) -> {got_missing!r}, "
                f"expected {{}} (the table is empty when no honest-test.toml exists)"
            )

    return bad


def run():
    bad = probe_read_config()
    for line in bad:
        print(line)
    print(f"probe_read_config: {len(bad)} failure(s)")
    return bad


if __name__ == "__main__":
    import sys

    sys.exit(1 if run() else 0)
