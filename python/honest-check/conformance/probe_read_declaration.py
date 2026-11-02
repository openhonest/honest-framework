"""read_declaration reads a named .hd from disk, parses it through honest-design's
read_hd, and returns the one parsed module (a Declaration) or a Fault.

Pins these outcomes against real temp files: a valid .hd returns a declaration
carrying a module whose functions include the declared `f`; an .hd that declares
two modules returns the first module, not the last; a missing path and a file of
unparseable junk each return a Fault (a record with 'problem' and 'remedy') whose
sentences name what went wrong and how to fix it, never a crash and never a clean
declaration. The Fault is honest-check's own {problem, remedy} record (section
HC-R002), a value that travels by return.
"""

import os
import tempfile

# A minimal valid module: one function f taking a str and returning a str. Kept
# valid enough that honest-design's read_hd returns {"ok": ...}.
_VALID_HD = "module m\n\n  fn f : (x: str) -> str\n"

# Two modules in one .hd: the first declares f, the second declares g. read_hd
# returns both, and read_declaration must return the first.
_TWO_MODULE_HD = (
    "module first\n\n  fn f : (x: str) -> str\n\n"
    "module second\n\n  fn g : (x: str) -> str\n"
)

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

    # Case 1 - a valid .hd returns a declaration carrying a module whose
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

    # Case 2 - a two-module .hd returns the first module, not the last. The first
    # module is named 'first' and declares f; the last is named 'second' and
    # declares g. Returning the last would carry name 'second' and function g.
    two_path = os.path.join(workdir, "two.hd")
    with open(two_path, "w", encoding="utf-8") as handle:
        handle.write(_TWO_MODULE_HD)
    got = read_declaration(two_path)
    if _is_fault(got) or not isinstance(got, dict) or "functions" not in got:
        bad.append(f"read_declaration({two_path!r}) -> {got!r}, expected the first declaration")
    else:
        names = [fn.get("name") for fn in got["functions"]]
        if got.get("name") != "first":
            bad.append(
                f"read_declaration({two_path!r}) -> module name {got.get('name')!r}, "
                f"expected 'first' (the first module, not the last)"
            )
        if "f" not in names or "g" in names:
            bad.append(
                f"read_declaration({two_path!r}) -> function names {names}, "
                f"expected only the first module's 'f', not the last module's 'g'"
            )

    # Case 3 - a missing path returns a Fault whose problem names the --declaration
    # path it could not read and whose remedy says to correct that path. An empty
    # problem or remedy string would not name the trouble, so the sentences must
    # carry their words.
    missing_path = os.path.join(workdir, "does_not_exist.hd")
    got = read_declaration(missing_path)
    if not _is_fault(got):
        bad.append(
            f"read_declaration({missing_path!r}) -> {got!r}, expected a Fault with 'problem' and 'remedy'"
        )
    else:
        if "named by --declaration" not in got["problem"]:
            bad.append(
                f"read_declaration({missing_path!r}) -> problem {got['problem']!r}, "
                f"expected it to say the path is 'named by --declaration'"
            )
        if "readable file" not in got["problem"]:
            bad.append(
                f"read_declaration({missing_path!r}) -> problem {got['problem']!r}, "
                f"expected it to say the path does not name a 'readable file'"
            )
        if "correct the --declaration path" not in got["remedy"]:
            bad.append(
                f"read_declaration({missing_path!r}) -> remedy {got['remedy']!r}, "
                f"expected it to say to 'correct the --declaration path'"
            )

    # Case 4 - a file of unparseable junk returns a Fault whose problem says
    # honest-design could not parse it and carries the parser's own error detail,
    # and whose remedy says to fix the declaration. The problem interpolates
    # repr(read_hd(junk)['err']); recomputing that detail here and demanding it in
    # the message pins the interpolated fragment, so emptying that fragment is
    # caught. An empty 'could not parse' lead or remedy is caught the same way.
    from honest_design import read_hd

    error_detail = repr(read_hd(_JUNK_HD).get("err"))
    junk_path = os.path.join(workdir, "junk.hd")
    with open(junk_path, "w", encoding="utf-8") as handle:
        handle.write(_JUNK_HD)
    got = read_declaration(junk_path)
    if not _is_fault(got):
        bad.append(
            f"read_declaration({junk_path!r}) -> {got!r}, expected a Fault with 'problem' and 'remedy'"
        )
    else:
        if "could not parse" not in got["problem"]:
            bad.append(
                f"read_declaration({junk_path!r}) -> problem {got['problem']!r}, "
                f"expected it to say honest-design 'could not parse' the declaration"
            )
        if error_detail not in got["problem"]:
            bad.append(
                f"read_declaration({junk_path!r}) -> problem {got['problem']!r}, "
                f"expected it to carry the parser's error detail {error_detail!r}"
            )
        if not got["problem"].rstrip().endswith("."):
            bad.append(
                f"read_declaration({junk_path!r}) -> problem {got['problem']!r}, "
                f"expected it to end with the error detail's trailing period"
            )
        if "fix the declaration" not in got["remedy"]:
            bad.append(
                f"read_declaration({junk_path!r}) -> remedy {got['remedy']!r}, "
                f"expected it to say to 'fix the declaration'"
            )

    return bad
