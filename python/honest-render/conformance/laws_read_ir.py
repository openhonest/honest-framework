# scenario: read_ir
# inherits: hd=python/honest-render/honest-render.hd::read_ir -> feature=specs/features/honest-render.feature::read_ir
"""honest-render conformance fragment for the `read_ir` scenario.

read_ir is honest-render's import seam to honest-design's read path -- its side of
`import honest_design` for the Module (the side it reads is honest-design.read_hd). It hands the
complete .hd source text to honest-design's read_hd and returns, as a bare union arm:

  - the Module intermediate representation honest-design read, on a valid declaration; or
  - honest-render's Fault, when read_hd reported the .hd is malformed or is not a valid
    declaration, passed through with its own code, message and category unchanged, recognized by
    is_fault, carried back by return (never raised, never wrapped in an ok/err envelope).

A readable document containing zero or two modules reports a not_single_module client
Fault with the count and a corrective message. Honest-render obtains the Module from Honest Design.

Why the expected values are honest. honest-design is a real dependency, so the probe calls the real
read_hd directly to learn what honest-design read (a DIFFERENT module's function, not the function
under test -- a pass-through check, not a circular oracle). The runtime read_hd was observed to
return an envelope: {"ok": Document} on a valid source, where Document["modules"] is the list of
Modules; and {"err": Fault} on a malformed source, where the Fault dict carries code/message/category
and is_fault recognizes it. read_ir's declared return is `Module | Fault` (a bare arm), so on a valid
source it must hand back the single bare Module honest-design read -- Document["modules"][0] -- not
the {"ok": ...} envelope and not the Document, and on a malformed source it must hand back the bare
Fault honest-design reported, not the {"err": ...} envelope.

The pass-through is also pinned with observed literals so a stub cannot pass: the valid module's name
is "m", and the malformed fault's code is "hd_syntax_error" with category "client" (honest-design's
own values, surfaced unchanged -- never re-coded to a render code such as file_unreadable).

Run:
  uv run --package honest-render python honest-render/conformance/laws_read_ir.py
"""

import re

from honest_design import read_hd
from honest_type import is_fault

from honest_render import read_ir


# A valid .hd module source: read_hd reads it cleanly; read_ir must hand back the bare Module.
_VALID_SOURCE = "module m\n  layer foundation\n"

# A malformed .hd source: read_hd reports its own fault; read_ir must pass that bare Fault through.
_MALFORMED_SOURCE = "module m\n  fn fn fn\n"
_WRONG_MODULE_COUNTS = (
    ("# this document declares no modules\n", "0"),
    ("module first\nmodule second\n", "2"),
)


def _design_module(source):
    """The single bare Module honest-design read -- the success arm read_ir must return.

    Calls the real honest-design read_hd (a different module, not the function under test) and
    unwraps its {"ok": Document} envelope to the one Module. This is the value read_ir surfaces.
    """
    return read_hd(source)["ok"]["modules"][0]


def _design_fault(source):
    """The bare Fault honest-design reported -- the fault arm read_ir must pass through unchanged.

    Unwraps the real read_hd's {"err": Fault} envelope to the one Fault.
    """
    return read_hd(source)["err"]


def probe_read_ir():
    """read_ir hands the source to honest-design's read_hd: on a valid declaration it returns the
    single bare Module honest-design read (not the ok envelope); on a malformed declaration it
    passes honest-design's bare Fault through unchanged (is_fault true, same code/message/category,
    never re-coded, no ok/err envelope)."""
    bad = []

    # 1. Valid declaration: the single bare Module honest-design read, not the {"ok": ...} envelope.
    got = read_ir(_VALID_SOURCE)
    expected_module = _design_module(_VALID_SOURCE)
    if got != expected_module:
        bad.append(f"read_ir(valid source) -> {got!r}, expected the bare Module {expected_module!r}")
    else:
        if not isinstance(got, dict):
            bad.append(f"read_ir(valid source) -> {got!r}, expected a Module record (dict)")
        else:
            if "ok" in got or "err" in got:
                bad.append(f"read_ir(valid source) returned an envelope {got!r}, expected a bare Module")
            # pinned literal: honest-design read a module named "m" from this source.
            if got.get("name") != "m":
                bad.append(f"read_ir(valid source) module name={got.get('name')!r}, expected 'm'")

    # 2. Malformed declaration: the bare Fault, recognized by is_fault, a union arm not an envelope.
    fault_got = read_ir(_MALFORMED_SOURCE)
    if not is_fault(fault_got):
        bad.append(f"read_ir(malformed source) -> {fault_got!r}, expected a Fault is_fault recognizes")
    else:
        design_fault = _design_fault(_MALFORMED_SOURCE)
        # code, message and category pass through unchanged from honest-design's read_hd.
        for field in ("code", "category", "message"):
            if fault_got.get(field) != design_fault[field]:
                bad.append(
                    f"read_ir(malformed source) fault {field}={fault_got.get(field)!r}, "
                    f"expected honest-design's {field}={design_fault[field]!r} unchanged"
                )
        # a bare union arm, never the {"err": ...} envelope.
        if "ok" in fault_got or "err" in fault_got:
            bad.append(f"read_ir(malformed source) returned an envelope {fault_got!r}, expected a bare Fault")
        # pinned literals: honest-design's own code/category, surfaced unchanged, never re-coded.
        if fault_got.get("code") != "hd_syntax_error":
            bad.append(f"read_ir(malformed source) code={fault_got.get('code')!r}, expected 'hd_syntax_error'")
        if fault_got.get("category") != "client":
            bad.append(f"read_ir(malformed source) category={fault_got.get('category')!r}, expected 'client'")

    for source, expected_count in _WRONG_MODULE_COUNTS:
        fault = read_ir(source)
        if not is_fault(fault) or fault.get("is_err") is not True or "ok" in fault or "err" in fault:
            bad.append(f"{expected_count} modules: expected a bare Fault with is_err true, got {fault!r}")
            continue
        if (fault.get("code"), fault.get("category")) != ("not_single_module", "client"):
            bad.append(f"{expected_count} modules: expected not_single_module/client, got {fault!r}")
        detail = fault.get("detail")
        if not isinstance(detail, dict) or expected_count not in detail.values():
            bad.append(f"{expected_count} modules: fault detail did not carry the observed count, got {detail!r}")
        message = fault.get("message")
        if not isinstance(message, str) or not re.search(r"\b(?:exactly|only|single|one)\b[^.;]*\bmodule\b|\b(?:individually|separately)\b", message, re.I):
            bad.append(f"{expected_count} modules: fault message did not explain the one-module requirement, got {message!r}")
        elif not re.search(r"\b(?:split|combine|add|remove|separate|merge|declare|provide|supply|render)\b", message, re.I):
            bad.append(f"{expected_count} modules: fault message did not offer a correction, got {message!r}")

    return bad


def run():
    failures = probe_read_ir()
    for f in failures:
        print(f"FAIL: read_ir: {f}")
    if not failures:
        print("ok: read_ir")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(run())
