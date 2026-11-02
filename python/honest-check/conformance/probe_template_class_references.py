"""template_class_references returns the static CSS classes a component template references
(honest-check.hd, spec section 3.5, HC-REF003). It is the public counterpart of the class
extraction check_references runs for HC-REF003: honest-test hands in one component's
template text and gets back one ClassRef { class } per static class token the template
emits, so it can prove two components do not share a CSS namespace (honest-test section 7.1).

Recognition matches HC-REF003: a `class="..."` attribute's value is split on whitespace
into tokens, and a value carrying interpolation (`class="card {{ variant }}"`) is skipped
whole, the stated bound of the check. Pins the contract: the tokens of a static class
value in source order, nothing from an interpolated value, and the empty list for a
template with no class. A stub returning [] fails cases 1 and 4.
"""

_CASES = [
    # A static class value: each whitespace-separated token in source order.
    {
        "template": '<div class="card primary"></div>',
        "want": [{"class": "card"}, {"class": "primary"}],
    },
    # An interpolated class value is skipped whole, so it contributes no class.
    {
        "template": '<span class="btn {{ variant }}">x</span>',
        "want": [],
    },
    # A template with no class attribute yields the empty list.
    {
        "template": "<p>no class here</p>",
        "want": [],
    },
    # Two class attributes across the template: every static token, in source order.
    {
        "template": '<a class="link"></a><b class="x y"></b>',
        "want": [{"class": "link"}, {"class": "x"}, {"class": "y"}],
    },
    # A non-class attribute contributes nothing: only the `class` attribute names CSS classes,
    # so an `id` (or any other attribute) value is not read as a class.
    {
        "template": '<div id="not-a-class" data-x="y">text</div>',
        "want": [],
    },
    # An empty class value has no attribute-value node to read: the extractor skips it and
    # yields no class, rather than reaching into an absent value.
    {
        "template": '<div class=""></div>',
        "want": [],
    },
    # A valueless (boolean-style) class attribute has no quoted value node: the extractor skips
    # it and yields no class, rather than reaching into an absent value node.
    {
        "template": "<div class></div>",
        "want": [],
    },
]


def probe_template_class_references():
    try:
        from honest_check.templates import template_class_references
    except ImportError as exc:
        return [
            f"cannot import template_class_references from honest_check.templates: {exc}"
        ]

    bad = []
    for case in _CASES:
        # The template arrives as bytes (the form honest-parse's parse takes and honest-test
        # holds a component template in); the cases are written as text for readability.
        got = template_class_references(case["template"].encode("utf-8"))
        if list(got) != case["want"]:
            bad.append(
                f"template_class_references over {case['template']!r} -> {got!r}, "
                f"expected {case['want']!r}"
            )
    return bad
