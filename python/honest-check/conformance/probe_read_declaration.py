"""Honest probe for honest-check's read_declaration (feature Scenario: read_declaration).

read_declaration reads the named .hd file's text and parses it through
honest-design's read_hd, returning the parsed Declaration on success and a raw
read-failure reason (a plain str, never honest-check's Fault) when the .hd is
missing or honest-design cannot parse it (return type Declaration | str).

The success case writes a real, valid .hd on disk and demands read_declaration
return exactly the Declaration honest-design's read_hd yields for it. The oracle
is built by calling honest-design directly — a different real module, not the
function under test — so the comparison is honest, not circular: it pins the
scenario's claim that read_declaration parses "through honest-design's read_hd"
and returns "the one parsed module". The two failure cases (an unparsable .hd, a
missing path) demand a plain str reason. No single trivial stub passes all three:
a str stub fails the success case (a Declaration dict != a str), and a non-str
stub fails the failure cases.
"""
import os
import tempfile

# A minimal .hd honest-design parses to exactly one module (one Declaration).
_VALID_HD = "module demo\n\n  layer domain\n\n  fn greet : (name: str) -> str\n"
# Source honest-design's read_hd refuses as malformed.
_BROKEN_HD = "this is not a module {{{\n"


def probe_read_declaration():
    """read_declaration returns the parsed Declaration on a valid .hd, else a raw str reason."""
    try:
        from honest_check import read_declaration
    except ImportError as exc:
        return [f"cannot import read_declaration: {exc}"]
    try:
        from honest_design import read_hd
    except ImportError as exc:
        return [f"cannot import honest_design.read_hd to build the oracle: {exc}"]

    bad = []

    # Success: a real valid .hd parses to the one Declaration honest-design yields.
    fd, path = tempfile.mkstemp(suffix=".hd")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(_VALID_HD)
        got = read_declaration(hd_path=path)
    finally:
        os.unlink(path)
    oracle = read_hd(_VALID_HD)["ok"]["modules"][0]
    if got != oracle:
        bad.append(
            f"read_declaration(valid .hd) -> {got!r}, "
            f"expected the parsed Declaration {oracle!r}"
        )

    # Failure: an unparsable .hd yields a raw str reason, never a Declaration.
    fd, path = tempfile.mkstemp(suffix=".hd")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(_BROKEN_HD)
        got = read_declaration(hd_path=path)
    finally:
        os.unlink(path)
    if not isinstance(got, str):
        bad.append(
            f"read_declaration(unparsable .hd) -> {got!r}, "
            f"expected a raw str read-failure reason"
        )

    # Failure: a missing path yields a raw str reason.
    missing = os.path.join(tempfile.gettempdir(), "no_such_module_probe_xyz.hd")
    if os.path.exists(missing):
        os.unlink(missing)
    got = read_declaration(hd_path=missing)
    if not isinstance(got, str):
        bad.append(
            f"read_declaration(missing .hd) -> {got!r}, "
            f"expected a raw str read-failure reason"
        )

    return bad
