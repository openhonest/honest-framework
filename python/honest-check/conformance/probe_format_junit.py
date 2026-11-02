"""format_junit renders JUnit XML: a <testsuites name="honest-check"> document with one
<testsuite>/<testcase>/<failure> per finding.

Each finding names its split file as the testsuite and testcase name, its rule and line
as the testcase name, its message as the failure message, and its line and context in
the failure body. Every open and close tag is present, and the document is joined with
newlines. A three-colon location splits from the right into file, line and col.
"""


def _diag(source_location, rule_id="HC-P003"):
    return {
        "rule_id": rule_id,
        "severity": "error",
        "message": "class declaration",
        "source_location": source_location,
        "context": "class X:",
        "fixable": False,
    }


def _report(diag):
    return {
        "diagnostics": [diag],
        "errors": 1,
        "warnings": 0,
        "infos": 0,
        "rule_counts": {},
        "adoption": "Declared",
        "enforced_count": 50,
        "total_count": 50,
        "report_mode": False,
    }


# Every line the one-finding document must carry, each pinning one tag's exact text and
# the split file, line, rule, message and context it renders.
_WANT_LINES = [
    '<testsuites name="honest-check">',
    '  <testsuite name="src/x.py" failures="1">',
    '    <testcase name="HC-P003:10" classname="src/x.py">',
    '      <failure message="class declaration">',
    "        Line 10: class X:",
    "      </failure>",
    "    </testcase>",
    "  </testsuite>",
    "</testsuites>",
]


def probe_format_junit():
    try:
        from honest_check import format_junit
        from honest_check.report import by_format
    except ImportError as exc:
        return [f"cannot import format_junit: {exc}"]

    bad = []
    got = format_junit(_report(_diag("src/x.py:10:1")))
    if not isinstance(got, str):
        return [f"format_junit(report) -> {got!r}, expected a string"]

    for want in _WANT_LINES:
        if want not in got:
            bad.append(f"format_junit is missing the line {want!r}; got {got!r}")

    # The document is joined with newlines, not run together.
    if "\n" not in got:
        bad.append(f"format_junit did not join its lines with newlines; got {got!r}")

    # A three-colon location splits from the right: file 'w:x', line 'y'. The testsuite
    # name ends at 'w:x' and the testcase name ends at the line 'y', rather than
    # swallowing the whole location.
    got3 = format_junit(_report(_diag("w:x:y:z", rule_id="HC-R001")))
    if '  <testsuite name="w:x" failures="1">' not in got3:
        bad.append(
            f"format_junit widened the right-split of a three-colon location; got {got3!r}"
        )
    if '<testcase name="HC-R001:y" classname="w:x">' not in got3:
        bad.append(
            f"format_junit did not render the split line in the testcase name; got {got3!r}"
        )

    # The format dispatch binds the junit word to this renderer.
    if by_format.get("junit") is not format_junit:
        bad.append(
            f"by_format['junit'] -> {by_format.get('junit')!r}, expected format_junit"
        )

    return bad
