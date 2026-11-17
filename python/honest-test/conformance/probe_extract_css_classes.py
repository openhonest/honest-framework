"""honest-test conformance: extract_css_classes.

extract_css_classes(template) -> set<str> pulls the CSS class names a component's
rendered HTML references out of its template, so test_css_isolation can intersect
one component's classes against another's (honest-test-architecture.md section 7.1).

A pure extractor: given a template string it returns exactly the set of class-attribute
tokens the markup uses. This probe calls the real function and asserts its exact output
on known templates. No classes, no mocks; every input is a real template string and the
function called is the real honest_test function.
"""

from honest_test import extract_css_classes


def probe_extract_css_classes():
    bad = []

    # A template that references four distinct classes across two class attributes.
    template = '<div class="card card__body"><p class="card__text note">hi</p></div>'
    got = extract_css_classes(template)
    if not isinstance(got, (set, frozenset)):
        bad.append(f"extract_css_classes should return a set, got {type(got).__name__}: {got!r}")
    else:
        expected = {"card", "card__body", "card__text", "note"}
        if set(got) != expected:
            bad.append(f"extract_css_classes({template!r}) -> {set(got)!r}, expected {expected!r}")

    # One class, one attribute.
    one = extract_css_classes('<span class="panel">x</span>')
    if set(one) != {"panel"}:
        bad.append(f"a single class should yield {{'panel'}}, got {set(one)!r}")

    # No class attribute anywhere.
    none = extract_css_classes("<section><p>plain text, no classes</p></section>")
    if set(none) != set():
        bad.append(f"a template with no class attribute should yield the empty set, got {set(none)!r}")

    # Repeated class across elements collapses to one member (a set, not a list).
    repeated = extract_css_classes('<a class="link">a</a><b class="link">b</b>')
    if set(repeated) != {"link"}:
        bad.append(f"a class used twice should appear once, got {set(repeated)!r}")

    return bad


def run():
    messages = probe_extract_css_classes()
    for message in messages:
        print(f"FAIL HT-probe [extract_css_classes]: {message}")
    print(f"extract_css_classes: {0 if messages else 1} passed, {1 if messages else 0} failed, 1 total")
    return 0 if not messages else 1


if __name__ == "__main__":
    raise SystemExit(run())
