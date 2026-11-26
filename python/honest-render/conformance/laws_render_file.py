# scenario: render_file
"""honest-render render_file: the one door, driven against the REAL door, the REAL honest-design
read_hd, and the REAL filesystem (no mock of our own code, no mock of honest-design, no patched
boundary).

render_file is the single input boundary (honest-render.hd render_file): it accepts a RenderRequest
carrying the .hd path and the chosen OutputTarget, hands it to exactly one orchestrator
(render_declaration), and adds nothing of its own. Signature (explorer module_ir):
  render_file(request: RenderRequest) -> str | Fault

Scenario (honest-render.feature, render_file) plus honest-render.hd section 3b:
  - it is the one door; it hands the request to one orchestrator and adds nothing of its own.
  - it returns the rendered document as a string on success.
  - it returns honest-render's Fault when honest-design's read_hd reported the .hd is malformed or
    is not a valid declaration, in which case NO document is rendered.
  - spec section 3b, the single-module rule carried by render_file's one orchestrator: honest-render
    renders EXACTLY ONE module per .hd. When honest-design's read_hd returns a Document carrying ZERO
    modules or MORE THAN ONE, there is not exactly one module to render, so render_file returns the
    CLIENT Fault whose code is `not_single_module`, category `client`, detail stating the module
    count found -- and renders nothing.
  - every fault travels back here by RETURN from the orchestrator as DATA, never raised.

Two literal, non-trivial pins this probe fixes, each confirmed against the REAL honest-design read_hd
(this test shaped its source strings by calling read_hd directly, below, not by assuming):
  - a ZERO-module .hd (an empty file): read_hd returns an ok Document carrying modules == [] (count
    0). render_file must return a Fault with code == "not_single_module", category == "client", and a
    detail that states the count 0.
  - a TWO-module .hd (two `module` declarations, alpha and beta): read_hd returns an ok Document
    carrying two modules (count 2). render_file must return a Fault with code == "not_single_module",
    category == "client", and a detail that states the count 2.
Neither is a read_hd fault: read_hd is happy with both, so this fault is honest-render's own, built
from the Document's module count -- the behaviour section 3b fixes and the module does not yet have.

Why this probe is not vacuous. A stub `def render_file(request): return ""` returns a str, which the
not_single_module rows reject (they require a Fault, not a document). A stub that returned any bare
Fault missing the fixed fields still fails: the rows pin code == "not_single_module",
category == "client", and that the detail text contains the exact module count. The malformed row is
the already-passing boundary/regression case (a genuine read_hd fault surfaced as data); it is not
the red-driver -- the two not_single_module rows are.

honest_type.is_fault is a framework primitive (it reads the reserved is_err tag), not honest-render's
own code under test, so depending on it is honest -- the module under test is render_file alone.

Gap: the scenario does NOT fix the exact rendered-document bytes for a valid single-module .hd, so no
success row pins a literal document string here; reported as a gap (owner: feature/hd).
"""

import tempfile
from pathlib import Path

import honest_render
from honest_type import is_fault


def _request(hd_path):
    """A RenderRequest to stdout, built as plain data (the record shapes honest-render.hd declares),
    not via any constructor under test and with no data-holding class. Every field is explicit:
    hd_path names the file; output is an OutputTarget whose path is NOTHING, written out as None,
    selecting the stdout side. No default kwarg stands in for the absent path."""
    return {"hd_path": hd_path, "output": {"path": None}}


# A genuinely malformed source: honest-design's read_hd reports it is not a valid declaration, and
# render_file passes that fault through as data (sections 3.3, 9). Kept as the boundary/regression
# case; already implemented, so it is not the red-driver.
_MALFORMED_HD = "this is not a valid .hd declaration at all {{{"

# A zero-module source: the empty file. Confirmed against the real honest-design read_hd that this
# yields an ok Document whose modules list is empty (count 0), NOT a read_hd fault.
_ZERO_MODULE_HD = ""

# A two-module source: two `module` declarations. Confirmed against the real honest-design read_hd
# that this yields an ok Document carrying two modules (count 2, names alpha and beta), NOT a fault.
_TWO_MODULE_HD = (
    "module alpha\n"
    "\n"
    "  layer tooling\n"
    "\n"
    "  fn a : () -> str\n"
    "\n"
    "module beta\n"
    "\n"
    "  layer tooling\n"
    "\n"
    "  fn b : () -> str\n"
)


# Each row names a real .hd file's text and what the one door must RETURN as data. "expect" is a
# claim about the returned value:
#   {"fault": True}  -- any honest-render Fault, surfaced as data (the malformed passthrough case).
#   {"fault": True, "code": ..., "category": ..., "count": n} -- a Fault with those exact fields and a
#   detail whose text states the module count n (the section 3b not_single_module cases).
_CASES = [
    {
        "name": "malformed_hd_passes_read_hd_fault_through_as_data",
        "hd_text": _MALFORMED_HD,
        "expect": {"fault": True},
    },
    {
        "name": "zero_module_hd_returns_client_not_single_module_count_0",
        "hd_text": _ZERO_MODULE_HD,
        "expect": {
            "fault": True,
            "code": "not_single_module",
            "category": "client",
            "count": 0,
        },
    },
    {
        "name": "two_module_hd_returns_client_not_single_module_count_2",
        "hd_text": _TWO_MODULE_HD,
        "expect": {
            "fault": True,
            "code": "not_single_module",
            "category": "client",
            "count": 2,
        },
    },
]


def probe_render_file():
    """render_file returns a Fault as data (never raised) and renders no document when there is not a
    single module to render: a read_hd fault passes through, and a Document carrying zero modules or
    more than one yields honest-render's client `not_single_module` Fault whose detail states the
    count (honest-render.hd section 3b)."""
    bad = []
    for case in _CASES:
        expect = case["expect"]
        with tempfile.TemporaryDirectory() as d:
            hd_path = str(Path(d) / "subject.hd")
            Path(hd_path).write_text(case["hd_text"])
            request = _request(hd_path)
            try:
                got = honest_render.render_file(request)
            except Exception as exc:  # the scenario forbids raising; the fault must return as data
                bad.append(
                    f"{case['name']}: render_file raised {type(exc).__name__}({exc!r}); section 3b "
                    f"requires the fault to travel back by return as data, never raised"
                )
                continue

            if isinstance(got, str):
                bad.append(
                    f"{case['name']}: render_file returned a document string {got!r}; this input has "
                    f"no single module to render, so it must render nothing and return a Fault"
                )
                continue
            if not is_fault(got):
                bad.append(
                    f"{case['name']}: render_file returned {got!r}, which is_fault rejects; it must "
                    f"return honest-render's Fault as data"
                )
                continue

            if "code" in expect and got.get("code") != expect["code"]:
                bad.append(
                    f"{case['name']}: Fault code is {got.get('code')!r}, expected {expect['code']!r} "
                    f"(section 3b: a Document that is not a single module is a {expect['code']} fault)"
                )
            if "category" in expect and got.get("category") != expect["category"]:
                bad.append(
                    f"{case['name']}: Fault category is {got.get('category')!r}, expected "
                    f"{expect['category']!r} (section 3b: not_single_module is a client fault)"
                )
            if "count" in expect:
                detail = got.get("detail")
                detail_text = "" if detail is None else " ".join(
                    [str(k) for k in detail.keys()] + [str(v) for v in detail.values()]
                ) if isinstance(detail, dict) else str(detail)
                if str(expect["count"]) not in detail_text:
                    bad.append(
                        f"{case['name']}: Fault detail {detail!r} does not state the module count "
                        f"{expect['count']}; section 3b requires the detail to state the count found"
                    )
    return bad


if __name__ == "__main__":
    failures = probe_render_file()
    if failures:
        print(f"RED probe_render_file: {len(failures)} failure(s)")
        for line in failures:
            print(f"  - {line}")
        raise SystemExit(1)
    print("GREEN probe_render_file")
