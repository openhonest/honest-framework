"""Honest probe for honest-check's format_junit (feature Scenario: format_junit).

format_junit renders a <testsuites name="honest-check"> JUnit XML document from a prepared
CheckReport, with one <testsuite> per file and a <testcase>/<failure> per finding. The .hd
note fixes the testcase name as '<rule id>:<line>' and the classname as '<file>'. It returns
the XML text and does no I/O.

The probe parses the XML back and asserts the structure. A stub returning "" fails to parse,
and a stub returning a bare document misses the testcase. The exact whitespace and element
ordering are not fixed, so the probe navigates the tree rather than matching a string.
"""
import xml.etree.ElementTree as ET


def _diag(rule_id, severity, message, source_location, context=""):
    return {
        "rule_id": rule_id,
        "severity": severity,
        "message": message,
        "source_location": source_location,
        "context": context,
        "fixable": False,
    }


_REPORT = {
    "diagnostics": [_diag("HC-P001", "error", "msg one", "src/x.py:10:5", "if a:")],
    "errors": 1,
    "warnings": 0,
    "infos": 0,
    "rule_counts": {},
    "adoption": "Declared",
    "enforced_count": 58,
    "total_count": 58,
    "report_mode": False,
}


def probe_format_junit():
    """format_junit renders a testsuites document with a testcase/failure per finding."""
    try:
        from honest_check import format_junit
    except ImportError as exc:
        return [f"cannot import format_junit: {exc}"]

    try:
        text = format_junit(report=_REPORT)
    except Exception as exc:
        return [f"format_junit raised {exc!r}"]

    try:
        root = ET.fromstring(text)
    except Exception as exc:
        return [f"format_junit output did not parse as XML ({exc!r}); got {text!r}"]

    bad = []
    if root.tag != "testsuites":
        bad.append(f"format_junit root tag -> {root.tag!r}, expected 'testsuites'")
    if root.get("name") != "honest-check":
        bad.append(f"format_junit testsuites name -> {root.get('name')!r}, expected 'honest-check'")

    suites = list(root.iter("testsuite"))
    if not suites:
        bad.append("format_junit has no <testsuite> element")

    match = None
    for case in root.iter("testcase"):
        if case.get("name") == "HC-P001:10" and case.get("classname") == "src/x.py":
            match = case
    if match is None:
        found = [(c.get("name"), c.get("classname")) for c in root.iter("testcase")]
        bad.append(
            "format_junit missing a <testcase> name='HC-P001:10' classname='src/x.py'; "
            f"found {found!r}"
        )
    elif match.find("failure") is None:
        bad.append("format_junit testcase for HC-P001 has no <failure> child")
    return bad
