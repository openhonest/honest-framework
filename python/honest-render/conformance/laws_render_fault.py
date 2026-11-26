# scenario: render_fault
"""honest-render render_fault law (one scenario, one fragment).

render_fault is the pure fault constructor: it assembles ONE honest-render Fault record from its
four parts (code, category, message, detail), sets the reserved is_err tag true, and returns the
Fault as a bare union arm (never raised, never wrapped in an ok/err envelope). The scenario fixes
every field of the built record:

  - is_err is true (the reserved arm tag, recognized by honest_type.is_fault)
  - code is the specific reason passed in: file_unreadable or write_failed, the two originated codes
  - category is the FaultCategory passed in: client for file_unreadable, server for write_failed
    (the two bounded values honest-type section 13.2 defines)
  - message is the human sentence passed in, carried through unchanged
  - detail is the structured context passed in, carried through unchanged

The two originated-fault codes from spec section 3b are pinned as literal cases, each with its fixed
category (file_unreadable -> client, write_failed -> server). The empty-detail case is written out
explicitly as detail {} -- never a default -- to pin that an empty dict is carried through unchanged.
Each _CASES row carries a literal whole-record expected value; no oracle recomputes it from the
function under test, so the probe is not vacuous.

A passed-through honest-design read_hd fault is NOT built here; that is render_declaration surfacing a
foreign fault, not render_fault's concern, so it is not a case here.

Run:
  uv run --package honest-render python honest-render/conformance/laws_render_fault.py
"""

from honest_render import render_fault

# Each row: the four parts render_fault is handed, and the whole Fault record it must return.
# is_err is always true (the reserved tag); code/category/message/detail are carried through.
_CASES = [
    # file_unreadable -> category client (spec section 3b).
    {
        "given": {
            "code": "file_unreadable",
            "category": "client",
            "message": "the .hd path could not be read; check the path and permissions",
            "detail": {"read_error": "No such file or directory: /x/missing.hd"},
        },
        "expect": {
            "is_err": True,
            "code": "file_unreadable",
            "category": "client",
            "message": "the .hd path could not be read; check the path and permissions",
            "detail": {"read_error": "No such file or directory: /x/missing.hd"},
        },
    },
    # write_failed -> category server (spec section 3b).
    {
        "given": {
            "code": "write_failed",
            "category": "server",
            "message": "the destination could not be written; check the output path",
            "detail": {"write_error": "Permission denied: /ro/out.md"},
        },
        "expect": {
            "is_err": True,
            "code": "write_failed",
            "category": "server",
            "message": "the destination could not be written; check the output path",
            "detail": {"write_error": "Permission denied: /ro/out.md"},
        },
    },
    # The explicit empty-detail boundary: a fault built with no structured context still carries the
    # four fields and the is_err tag; detail is the empty dict written out, never a default.
    {
        "given": {
            "code": "file_unreadable",
            "category": "client",
            "message": "the .hd path could not be read",
            "detail": {},
        },
        "expect": {
            "is_err": True,
            "code": "file_unreadable",
            "category": "client",
            "message": "the .hd path could not be read",
            "detail": {},
        },
    },
]


def probe_render_fault():
    """render_fault builds one honest-render Fault from its parts: is_err true, and code, category,
    message and detail carried through unchanged (file_unreadable->client, write_failed->server)."""
    bad = []
    for case in _CASES:
        got = render_fault(**case["given"])
        if got != case["expect"]:
            bad.append(f"render_fault({case['given']}) -> {got!r}, expected {case['expect']!r}")
    return bad


def run():
    failures = probe_render_fault()
    for f in failures:
        print(f"FAIL: {f}")
    if not failures:
        print("ok: render_fault")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(run())
