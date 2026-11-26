# scenario: cross_declaration
# inherits: hd=python/honest-check/honest-check.hd::cross_declaration -> feature=specs/features/honest-check.feature::cross_declaration
# inherits: hd=python/honest-check/honest-check.hd::check_references -> feature=specs/features/honest-check.feature::check_references
# inherits: hd=python/honest-check/honest-check.hd::check_roles -> feature=specs/features/honest-check.feature::check_roles
"""Boundary cases for crossing helpers whose ordinary examples are insufficient.

These cases pin distinctions that are easy to erase in the crossing implementation:
the explicit ``None`` absence vocabulary, a non-string route field, and a dispatch
value that merely spells a function name.
"""


def _module(hd):
    from honest_design import read_hd

    parsed = read_hd(hd)
    return parsed["ok"]["modules"][0]


def probe_crossing_survivors():
    """Crossing helpers preserve absence, syntax and dispatch distinctions."""
    from honest_check import check_references, check_roles, cross_declaration, pair_source

    failures = []

    # HC-R004: the declaration's explicit None arm is an absence vocabulary too.
    hd = _module(
        'module demo\n  layer correctness\n'
        '  fn find : () -> int | None note "may return no value"\n'
    )
    findings = cross_declaration(
        [pair_source("demo.py", b"def find():\n    return None\n")],
        hd,
        b"",
        ["HC-R004"],
    )
    if findings:
        failures.append(f"explicit None absence arm produced {findings!r}")

    # HC-REF001/_dict_string: a route with a non-string method field does not mount.
    sources = [
        pair_source(
            "routes.py",
            b"def route_table():\n    return [{'method': 7, 'path': '/ok'}]\n",
        ),
        pair_source("page.html", b'<a hx-get="/ok">go</a>\n'),
    ]
    findings = check_references(sources, None)
    if [f["rule_id"] for f in findings] != ["HC-REF001"]:
        failures.append(f"non-string route method produced {findings!r}, expected one HC-REF001")

    # HC-R001 dispatch values are bare identifiers only: a string spelling a
    # function name must not make that function reachable.
    source = (
        b"@orchestrator\n"
        b"def run(kind): return handlers[kind]\n"
        b"def picked(): pass\n"
        b"handlers = {'only': 'picked'}\n"
    )
    findings = check_roles([pair_source("mod.py", source)], None)
    if [f["rule_id"] for f in findings] != ["HC-R001"] or "picked" not in findings[0]["context"]:
        failures.append(f"literal dispatch value produced {findings!r}, expected picked orphan")

    return failures
