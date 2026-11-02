"""check_references folds the two cross-file reference rules over the whole set of
template, stylesheet and script files and returns the dead references as data. This
probe is the test-of-record for HC-REF002 and HC-REF003: both resolve references
that cross files (an include target in a sibling root, a class defined by any
component's stylesheet), so neither can be pinned by the single-source conformance
suite the way check_source's per-file rules are.

Each case builds its own small multi-file `sources` list inline, calls the real
check_references over it, and checks the findings two ways: the set of
(rule_id, severity) pairs over the whole returned list equals the set the case
fixes, and every expected finding points at the offending file (its path appears in
the diagnostic's source_location), so a case does not depend on an exact column.

A stub returning [] passes the clean and dynamic-skip cases but fails every firing
case, so the probe is not vacuous.

Spec authorities: §HC-REF002 (template include/extends target resolves to a
template), §HC-REF003 (template/script class reference resolves to a defined rule).
Both fire at severity 'error' (section 8). A dynamic include target
(`{% include some_var %}`) and an interpolated class value (`class="card {{ variant }}"`)
are skipped whole, the stated bound of each check.
"""

# Each case: a name, the multi-file sources list, and the findings it fixes as
# (rule_id, severity, offending_path) triples. The clean and dynamic-skip cases fix
# the empty list, written out, because the scenario names them explicitly.
_CASES = [
    # HC-REF002 fires — main.html includes a template no source provides.
    {
        "name": "HC-REF002 fires (include target missing)",
        "sources": [
            {"path": "main.html", "text": '{% include "missing.html" %}\n'},
            {"path": "button.html", "text": "<button>go</button>\n"},
        ],
        "want": [("HC-REF002", "error", "main.html")],
    },
    # HC-REF002 clean — the included template is among the sources.
    {
        "name": "HC-REF002 clean (include target present)",
        "sources": [
            {"path": "main.html", "text": '{% include "button.html" %}\n'},
            {"path": "button.html", "text": "<button>go</button>\n"},
        ],
        "want": [],
    },
    # HC-REF003 fires — template emits class="card" and no stylesheet defines .card.
    {
        "name": "HC-REF003 fires (template class undefined)",
        "sources": [
            {"path": "main.html", "text": '<div class="card">x</div>\n'},
        ],
        "want": [("HC-REF003", "error", "main.html")],
    },
    # HC-REF003 fires — a script adds class "card" and no stylesheet defines .card.
    {
        "name": "HC-REF003 fires (script classList.add undefined)",
        "sources": [
            {"path": "app.js", "text": 'element.classList.add("card");\n'},
        ],
        "want": [("HC-REF003", "error", "app.js")],
    },
    # HC-REF003 clean — a stylesheet defines .card and the template uses it.
    {
        "name": "HC-REF003 clean (stylesheet defines class)",
        "sources": [
            {"path": "main.html", "text": '<div class="card">x</div>\n'},
            {"path": "card.css", "text": ".card { color: red; }\n"},
        ],
        "want": [],
    },
    # Dynamic/interpolated skips — a variable include target and an interpolated
    # class value both carry no literal to resolve, so neither rule fires even
    # though no missing.html template and no .card rule exist.
    {
        "name": "dynamic include and interpolated class are skipped",
        "sources": [
            {
                "path": "main.html",
                "text": "{% include some_var %}\n"
                '<div class="card {{ variant }}">x</div>\n',
            },
        ],
        "want": [],
    },
    # A file of an unplaceable extension is ignored, and a jinja tag that is not
    # include/extends ({% if %}) carries no template target to resolve.
    {
        "name": "unplaceable file and non-include jinja tag are ignored",
        "sources": [
            {"path": "notes.txt", "text": "hello\n"},
            {"path": "main.html", "text": "{% if x %}y{% endif %}\n"},
        ],
        "want": [],
    },
    # HTML attributes that are not class, an empty class value, and a class attribute
    # with no value all carry no static class token to resolve.
    {
        "name": "non-class, empty, and valueless class attributes carry no token",
        "sources": [
            {
                "path": "m.html",
                "text": '<div id="q">z</div>\n<p class="">y</p>\n<span class>w</span>\n',
            },
        ],
        "want": [],
    },
    # classList-shaped JavaScript that is not actually a classList.<method>(literal)
    # call contributes no class token: a plain call, a non-classList method, an
    # identifier receiver, the wrong receiver property, and a dynamic argument.
    {
        "name": "non-classList script calls contribute no class token",
        "sources": [
            {
                "path": "a.js",
                "text": 'foo("card");\nel.classList.sort("card");\nobj.add("card");\n'
                "el.other.add(\"card\");\nel.classList.add(variant);\n",
            },
        ],
        "want": [],
    },
    # className assignments that are not a string literal to a `.className` member:
    # a plain name target, a non-string right side, and the wrong property.
    {
        "name": "non-className script assignments contribute no class token",
        "sources": [
            {
                "path": "b.js",
                "text": 'x = "card";\nel.className = foo;\nel.other = "card";\n',
            },
        ],
        "want": [],
    },
    # HC-REF003 fires — a script assigns the literal class "card" to .className and no
    # stylesheet defines it.
    {
        "name": "HC-REF003 fires (script className assignment undefined)",
        "sources": [
            {"path": "c.js", "text": 'el.className = "card";\n'},
        ],
        "want": [("HC-REF003", "error", "c.js")],
    },
]


def _pairs(findings):
    """The (rule_id, severity) set a run produced, as a sorted list for comparison."""
    return sorted((d.get("rule_id"), d.get("severity")) for d in findings)


def _want_pairs(want):
    """The (rule_id, severity) set a case fixes, as a sorted list."""
    return sorted((rule_id, severity) for rule_id, severity, _ in want)



# ---- full-record pinning: the probe above asserts only (rule_id, severity)
# and the offending path; these cases pin the whole Diagnostic record of each
# variant, so emptying a message/key literal, flipping fixable, or swapping a
# dict key changes the record and fails here.
_MSG_CASES = [
    {
        "id": 'HC-REF002',
        "sources": [{'path': 'main.html', 'text': '{% include "missing.html" %}\n'}],
        "expected": [{'rule_id': 'HC-REF002', 'severity': 'error', 'message': "template include target 'missing.html' resolves to no template among the checked files. Add the template, or correct the target.", 'source_location': 'main.html:1:1', 'context': '', 'fixable': False}],
    },
    {
        "id": 'HC-REF002-extends',
        "sources": [{'path': 'main.html', 'text': '{% extends "missing.html" %}\n'}],
        "expected": [{'rule_id': 'HC-REF002', 'severity': 'error', 'message': "template extends target 'missing.html' resolves to no template among the checked files. Add the template, or correct the target.", 'source_location': 'main.html:1:1', 'context': '', 'fixable': False}],
    },
    {
        "id": 'HC-REF003-template',
        "sources": [{'path': 'main.html', 'text': '<div class="card">x</div>\n'}],
        "expected": [{'rule_id': 'HC-REF003', 'severity': 'error', 'message': "class 'card' resolves to no rule any stylesheet defines. Define the class, or correct the reference.", 'source_location': 'main.html:1:12', 'context': '', 'fixable': False}],
    },
    {
        "id": 'HC-REF003-script-add',
        "sources": [{'path': 'app.js', 'text': 'element.classList.add("card");\n'}],
        "expected": [{'rule_id': 'HC-REF003', 'severity': 'error', 'message': "class 'card' resolves to no rule any stylesheet defines. Define the class, or correct the reference.", 'source_location': 'app.js:1:1', 'context': '', 'fixable': False}],
    },
    {
        "id": 'HC-REF003-script-remove',
        "sources": [{'path': 'app.js', 'text': 'element.classList.remove("card");\n'}],
        "expected": [{'rule_id': 'HC-REF003', 'severity': 'error', 'message': "class 'card' resolves to no rule any stylesheet defines. Define the class, or correct the reference.", 'source_location': 'app.js:1:1', 'context': '', 'fixable': False}],
    },
    {
        "id": 'HC-REF003-script-toggle',
        "sources": [{'path': 'app.js', 'text': 'element.classList.toggle("card");\n'}],
        "expected": [{'rule_id': 'HC-REF003', 'severity': 'error', 'message': "class 'card' resolves to no rule any stylesheet defines. Define the class, or correct the reference.", 'source_location': 'app.js:1:1', 'context': '', 'fixable': False}],
    },
    {
        "id": 'HC-REF003-script-replace',
        "sources": [{'path': 'app.js', 'text': 'element.classList.replace("card");\n'}],
        "expected": [{'rule_id': 'HC-REF003', 'severity': 'error', 'message': "class 'card' resolves to no rule any stylesheet defines. Define the class, or correct the reference.", 'source_location': 'app.js:1:1', 'context': '', 'fixable': False}],
    },
    {
        "id": 'HC-REF003-script-contains',
        "sources": [{'path': 'app.js', 'text': 'element.classList.contains("card");\n'}],
        "expected": [{'rule_id': 'HC-REF003', 'severity': 'error', 'message': "class 'card' resolves to no rule any stylesheet defines. Define the class, or correct the reference.", 'source_location': 'app.js:1:1', 'context': '', 'fixable': False}],
    },
    {
        "id": 'basename-resolving',
        "sources": [{'path': 'page.html', 'text': '{% include "main.html" %}\n'}, {'path': 'sub/main.html', 'text': '<b>y</b>\n'}],
        "expected": [],
    },
]

def _canon(diags):
    import json
    return sorted(json.dumps(d, sort_keys=True) for d in diags)


def _message_failures():
    from honest_check import check_references
    bad = []
    for case in _MSG_CASES:
        got = check_references(case["sources"])
        if _canon(got) != _canon(case["expected"]):
            bad.append(f"record pinning {case['id']!r}: got {_canon(got)}, expected {_canon(case['expected'])}")
    return bad

def probe_check_references():
    """check_references reports every dead include/extends target and every dead
    static class reference across the whole file set as an error Diagnostic that
    points at the offending file, and reports nothing for a target or class that
    resolves or carries no literal to resolve."""
    try:
        from honest_check import check_references
    except ImportError as exc:
        return [f"cannot import check_references: {exc}"]

    bad = []
    for case in _CASES:
        got = check_references(case["sources"])
        if not isinstance(got, list):
            bad.append(f"{case['name']}: check_references -> {got!r}, expected a list")
            continue

        got_pairs = _pairs(got)
        want_pairs = _want_pairs(case["want"])
        if got_pairs != want_pairs:
            bad.append(
                f"{case['name']}: (rule_id, severity) pairs {got_pairs}, "
                f"expected {want_pairs}"
            )

        for rule_id, severity, path in case["want"]:
            pointed = [
                d
                for d in got
                if d.get("rule_id") == rule_id
                and d.get("severity") == severity
                and path in str(d.get("source_location", ""))
            ]
            if not pointed:
                locations = [
                    (d.get("rule_id"), d.get("source_location")) for d in got
                ]
                bad.append(
                    f"{case['name']}: no {rule_id} {severity} finding points at "
                    f"{path!r}; findings were {locations}"
                )
    bad.extend(_message_failures())
    return bad
