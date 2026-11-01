"""read_declaration reads a named .hd from disk, parses it through honest-design's
read_hd, and returns the one parsed module (a Declaration) or a Fault.

Pins three outcomes against real temp files: a valid .hd returns a declaration
carrying a module whose functions include the declared `f`; a missing path and a
file of unparseable junk each return a Fault (a record with 'problem' and
'remedy'), never a crash and never a clean declaration. The Fault is honest-check's
own {problem, remedy} record (§HC-R002), a value that travels by return.
"""

import os
import tempfile

# A minimal valid module: one function f taking a str and returning a str. Kept
# valid enough that honest-design's read_hd returns {"ok": ...}.
_VALID_HD = "module m\n\n  fn f : (x: str) -> str\n"

# Not an .hd at all: honest-design's read_hd must fail to parse this.
_JUNK_HD = "this is not a declaration {{{ >>> @@@ \n"


def _is_fault(value):
    """A Fault is honest-check's {problem, remedy} record, both strings."""
    return (
        isinstance(value, dict)
        and isinstance(value.get("problem"), str)
        and isinstance(value.get("remedy"), str)
    )


def probe_read_declaration():
    try:
        from honest_check import read_declaration
    except ImportError as exc:
        return [f"cannot import read_declaration: {exc}"]

    bad = []
    workdir = tempfile.mkdtemp(prefix="hc_read_decl_")

    # Case 1 — a valid .hd returns a declaration carrying a module whose
    # functions include f.
    valid_path = os.path.join(workdir, "m.hd")
    with open(valid_path, "w", encoding="utf-8") as handle:
        handle.write(_VALID_HD)
    got = read_declaration(valid_path)
    if _is_fault(got):
        bad.append(f"read_declaration({valid_path!r}) -> Fault {got!r}, expected a parsed declaration")
    elif not isinstance(got, dict) or "functions" not in got:
        bad.append(f"read_declaration({valid_path!r}) -> {got!r}, expected a declaration with functions")
    else:
        names = [fn.get("name") for fn in got["functions"]]
        if "f" not in names:
            bad.append(
                f"read_declaration({valid_path!r}) -> function names {names}, expected 'f' among them"
            )

    # Case 2 — a missing path returns a Fault, not a crash and not a declaration.
    missing_path = os.path.join(workdir, "does_not_exist.hd")
    got = read_declaration(missing_path)
    if not _is_fault(got):
        bad.append(
            f"read_declaration({missing_path!r}) -> {got!r}, expected a Fault with 'problem' and 'remedy'"
        )

    # Case 3 — a file of unparseable junk returns a Fault, not a clean declaration.
    junk_path = os.path.join(workdir, "junk.hd")
    with open(junk_path, "w", encoding="utf-8") as handle:
        handle.write(_JUNK_HD)
    got = read_declaration(junk_path)
    if not _is_fault(got):
        bad.append(
            f"read_declaration({junk_path!r}) -> {got!r}, expected a Fault with 'problem' and 'remedy'"
        )

    return bad
