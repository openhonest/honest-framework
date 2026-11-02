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
]


def _pairs(findings):
    """The (rule_id, severity) set a run produced, as a sorted list for comparison."""
    return sorted((d.get("rule_id"), d.get("severity")) for d in findings)


def _want_pairs(want):
    """The (rule_id, severity) set a case fixes, as a sorted list."""
    return sorted((rule_id, severity) for rule_id, severity, _ in want)


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
    return bad
