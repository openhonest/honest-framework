"""RED probe for honest-test.read_config — the config reader (.hd, sections 3.6, 10).

read_config reads honest-test.toml once and decodes it to the plain parsed table —
a map of maps — building no record and resolving nothing. The table is empty when
no honest-test.toml exists. The probe writes a real honest-test.toml, reads it,
and checks the decode against the known content, then checks the missing-file case.
honest-test has no code yet, so importing honest_test fails — the correct red state.
"""

import os
import tempfile

from honest_test import read_config


def probe_read_config():
    """read_config decodes an existing honest-test.toml to the plain TOML table and
    returns the empty table when the file does not exist."""
    bad = []

    toml_text = (
        "[runner]\n"
        "parallel = true\n"
        "timeout_seconds = 30\n"
        "\n"
        "[predicates.customer_id]\n"
        'valid = ["CUST-00001", "CUST-99999"]\n'
        'invalid = ["CUST-0", "cust-00001"]\n'
        'strategy = "supplied_only"\n'
    )
    expected = {
        "runner": {"parallel": True, "timeout_seconds": 30},
        "predicates": {
            "customer_id": {
                "valid": ["CUST-00001", "CUST-99999"],
                "invalid": ["CUST-0", "cust-00001"],
                "strategy": "supplied_only",
            }
        },
    }

    handle, path = tempfile.mkstemp(suffix=".toml")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as f:
            f.write(toml_text)

        got = read_config(path)
        if not isinstance(got, dict):
            bad.append(f"read_config returned {type(got).__name__}, expected a dict (the decoded TOML table)")
        elif got != expected:
            bad.append(f"read_config decoded to {got!r}, expected the plain table {expected!r}")
    finally:
        os.unlink(path)

    # A path to a honest-test.toml that does not exist yields the empty table.
    missing_dir = tempfile.mkdtemp()
    missing_path = os.path.join(missing_dir, "honest-test.toml")
    try:
        got = read_config(missing_path)
        if got != {}:
            bad.append(f"a missing honest-test.toml should decode to the empty table, got {got!r}")
    finally:
        os.rmdir(missing_dir)

    return bad


def run():
    failures = probe_read_config()
    for message in failures:
        print(f"FAIL read_config: {message}")
    print(f"read_config probe: {'PASS' if not failures else str(len(failures)) + ' failed'}")
    return failures


if __name__ == "__main__":
    raise SystemExit(1 if run() else 0)
