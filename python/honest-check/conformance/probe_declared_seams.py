"""declared_seams collects every cross-module seam one module declares into a
list of Seam records, the one derivation HC-REF006 and HC-REF007 share.

Pins two cases. Each gives a tiny valid .hd (parsed through honest-design's
read_hd, which is not the function under test) for one module, and the exact
list of Seam records declared_seams must return. The firing case names a
`callee.door` side effect and expects one Seam carrying that caller, module,
door and direction; the absence case names only the world (reads "clock") and
expects []. A stub returning [] fails the firing case.

Spec authority: §HC-REF006/HC-REF007 declaration (honest-check.hd, declared_seams).
"""

# Each case: the caller module's .hd and the exact seam list it must yield.
_CASES = [
    # A seam into another module's door yields one Seam carrying the caller
    # function name, the named module, the door, and the direction verbatim.
    {
        "name": "one seam into callee.door",
        "hd": 'module caller\n\n  reader fn f : (r: str) -> str side_effect reads "callee.door"\n',
        "expect": [
            {"caller": "f", "module": "callee", "door": "door", "direction": "reads"}
        ],
    },
    # A side effect that names the world carries no module to resolve, so the
    # module declares no seam: the explicit absence case.
    {
        "name": "only a world side effect",
        "hd": 'module caller\n\n  fn w : (x: str) -> str side_effect reads "clock"\n',
        "expect": [],
    },
]


def probe_declared_seams():
    try:
        from honest_check.integration_rules import declared_seams
    except ImportError as exc:
        return [f"cannot import declared_seams: {exc}"]
    from honest_design import read_hd

    bad = []
    for case in _CASES:
        parsed = read_hd(case["hd"])
        if "ok" not in parsed:
            bad.append(f"{case['name']}: fixture .hd did not parse: {parsed.get('err')!r}")
            continue
        module = parsed["ok"]["modules"][0]

        got = declared_seams(module)
        if not isinstance(got, list):
            bad.append(f"{case['name']}: declared_seams -> {got!r}, expected a list")
            continue

        # Compare the fields the Seam record pins, order-independent, so an
        # extra key on the record does not fail the behavioural claim.
        got_rows = sorted(
            (
                s.get("caller"),
                s.get("module"),
                s.get("door"),
                s.get("direction"),
            )
            for s in got
        )
        want_rows = sorted(
            (s["caller"], s["module"], s["door"], s["direction"])
            for s in case["expect"]
        )
        if got_rows != want_rows:
            bad.append(
                f"{case['name']}: declared_seams -> {got_rows}, expected {want_rows}"
            )
    return bad
