"""Conformance fragment for the extract_css_classes scenario (honest-test.feature).

Scenario: extract_css_classes pulls the CSS class names out of a component's
  template.
  Then it returns the set of class names the component's rendered-HTML template
  references, for test_css_isolation to intersect against another component's
  (section 7.1). It reads no world and returns pure data.

Cases are data; one pure probe feeds them to the real function and returns a list
of failure strings (empty when every case holds). No classes, no mocks: it calls
the real honest_test.extract_css_classes on literal HTML templates and compares
the returned set of class names against the literal set written out per case.

The .hd note is silent on single- vs double-quoted class attributes, so every
template below uses double quotes (see the Gaps block in the report). The return
is set<str>, so each case compares as a set.

This is its own fragment file so the other scenarios' fragments never collide with
it. run_conformance.py / laws_htest.py are untouched.
"""

from honest_test import extract_css_classes

_CASES = [
    # (a) a single element with one class
    {"given": {"template": '<div class="card"></div>'}, "expect": {"card"}},
    # (b) multiple classes on one element
    {
        "given": {"template": '<div class="card card--active"></div>'},
        "expect": {"card", "card--active"},
    },
    # (c) classes across several elements
    {
        "given": {"template": '<div class="a"><span class="b c"></span></div>'},
        "expect": {"a", "b", "c"},
    },
    # (d) a template with no class attributes -> the explicit empty set
    {"given": {"template": "<div><span>hello</span></div>"}, "expect": set()},
    # (e) duplicate class names across elements collapse to one set entry
    {
        "given": {"template": '<p class="x"></p><p class="x"></p>'},
        "expect": {"x"},
    },
]


def probe_extract_css_classes():
    """extract_css_classes returns the set of CSS class names a component's template references, collapsing duplicates and yielding the empty set when there are none."""
    bad = []
    for case in _CASES:
        got = extract_css_classes(**case["given"])
        if got != case["expect"]:
            bad.append(
                f"extract_css_classes({case['given']}) -> {got}, "
                f"expected {case['expect']}"
            )
    return bad


def run():
    bad = probe_extract_css_classes()
    for line in bad:
        print(line)
    print(f"probe_extract_css_classes: {len(bad)} failure(s)")
    return bad


if __name__ == "__main__":
    import sys

    sys.exit(1 if run() else 0)
