# scenario: check_references
# inherits: hd=python/honest-check/honest-check.hd::check_references -> feature=specs/features/honest-check.feature::check_references
"""Honest probe for honest-check's check_references (feature Scenario: check_references).

check_references resolves cross-file references over the whole discovered set and
returns a list<Diagnostic>, all four reference rules at error severity. This probe
pins each of the four with a literal dead reference and gives the matching clean case:

- HC-REF001 resolves each template hx-* action site against the route map the
  code's route_table() data declares (§HC-REF001). The set holds a code file whose
  route_table() mounts GET /home; a template emitting `hx-get="/ghost"` targets a
  (GET, /ghost) no route mounts, a dead reference -> one HC-REF001 error. The clean
  template targets `hx-get="/home"`, which the map mounts -> no diagnostic. (A set
  with no route_table() stands HC-REF001 down, so the code file is required to arm
  the rule.)
- HC-REF002 resolves a template's include/extends target against the template
  set. A literal `{% extends "no_such_base.html" %}` matches no template in the
  set under any loader root, so it is a dead reference -> one HC-REF002 error.
- HC-REF003 resolves each static class a template emits against the union of the
  class selectors every discovered stylesheet defines. With no stylesheet in the
  set that union is empty, so an emitted `class="ghostclass"` is defined nowhere
  -> one HC-REF003 error. (The .hd gives HC-REF003 no stand-down clause for an
  empty stylesheet set, unlike HC-REF001's empty route map and HC-REF004's
  NOTHING arm.)
- HC-REF004 resolves each authored hf-* value whose attribute the vocabulary
  enumerates against that attribute's allowed set (§HC-REF004). With
  format_vocabulary {"hf-format": ["currency", "percent"]}, a template emitting
  `hf-format="bogus"` names no member -> one HC-REF004 error. The clean template
  emits `hf-format="currency"`, a member -> no diagnostic. Both templates use
  a class declared in a stylesheet supplied alongside them, so their CSS reference
  also resolves.
- The plain clean case is a template with no include, no class, no hx-* action
  and no hf-* value, with format_vocabulary standing HC-REF004 down -> no
  diagnostics.

A stub `return []` passes every clean case and fails every dead-reference case, so
each dead case is a non-trivial literal no empty body produces. Inputs are real
SourceFile records: {path, text} with raw bytes, the shape honest-check reads.

NOTHING is spelled as Python None here (the FormatVocabulary | NOTHING absence
arm); see the GAPS note.
"""

# A code file whose route_table() mounts GET /home, the route map HC-REF001 reads.
_SRC_ROUTES = {
    "path": "routes.py",
    "text": b'def route_table():\n    return [{"method": "GET", "path": "/home", "chain": "home"}]\n',
}
# A template whose hx-get action targets a route the map does not mount: a dead reference.
_SRC_DEAD_ACTION = {
    "path": "action.html",
    "text": b'<div hx-get="/ghost">x</div>\n',
}
# A template whose hx-get action targets the mounted route: resolves.
_SRC_LIVE_ACTION = {
    "path": "action.html",
    "text": b'<div hx-get="/home">x</div>\n',
}
# The stylesheet defines the class used by the format examples in another source.
_SRC_FORMAT_CSS = {
    "path": "format.css",
    "text": b".formatted-amount { color: black; }\n",
}
# A template whose hf-format value names no member of the enumerated vocabulary: a dead reference.
_SRC_DEAD_HF = {
    "path": "format.html",
    "text": b'<span class="formatted-amount" hf-format="bogus">x</span>\n',
}
# A template whose hf-format value is a declared member: resolves.
_SRC_LIVE_HF = {
    "path": "format.html",
    "text": b'<span class="formatted-amount" hf-format="currency">x</span>\n',
}
# The format vocabulary HC-REF004 resolves hf-* values against.
_FMT = {"hf-format": ["currency", "percent"]}

# A template whose extends target names no template in the set: a dead reference.
_SRC_DEAD_EXTENDS = {
    "path": "page.html",
    "text": b'{% extends "no_such_base.html" %}\n',
}
# A template emitting a class no stylesheet defines (the set holds no stylesheet).
_SRC_DEAD_CLASS = {
    "path": "widget.html",
    "text": b'<div class="ghostclass">x</div>\n',
}
# A plain template with no resolvable reference of any kind.
_SRC_CLEAN = {
    "path": "clean.html",
    "text": b"<html><body><p>Hello</p></body></html>\n",
}

# Each case: the SourceFile list, the format_vocabulary (None = NOTHING, standing
# HC-REF004 down), and the (rule_id, severity) pairs check_references must return.
_CASES = [
    {"sources": [_SRC_ROUTES, _SRC_DEAD_ACTION], "fmt": None, "expect": [("HC-REF001", "error")], "action": ("GET", "/ghost")},
    {"sources": [_SRC_ROUTES, _SRC_LIVE_ACTION], "fmt": None, "expect": []},
    {
        "sources": [
            {"path": "service.py", "text": b"def home():\n    return 'home'\n"},
            _SRC_DEAD_ACTION,
        ],
        "fmt": None,
        "expect": [],
    },
    {
        "sources": [
            {"path": "routes.py", "text": b'def route_table():\n    return [{"method": "POST", "path": "/items/{id}"}]\n'},
            {"path": "action.htm", "text": b'<button hx-post="/items/{{item.id}}">Save</button>\n'},
        ],
        "fmt": None,
        "expect": [],
    },
    {
        "sources": [
            {"path": "routes.py", "text": b'def route_table():\n    return [{"method": "POST", "path": "/items/{id}"}]\n'},
            {"path": "action.htm", "text": b'<button hx-get="/items/{{item.id}}">Save</button>\n'},
        ],
        "fmt": None,
        "expect": [("HC-REF001", "error")],
        "action": ("GET", "/items/{{item.id}}"),
    },
    {
        "sources": [
            {"path": "routes.py", "text": b'def route_table():\n    return [{"method": "GET", "path": "/items/"}]\n'},
            {"path": "action.htm", "text": b'<button hx-get="/items/{{item.id}}">View</button>\n'},
        ],
        "fmt": None,
        "expect": [("HC-REF001", "error")],
        "action": ("GET", "/items/{{item.id}}"),
    },
    {
        "sources": [
            {"path": "pages/view.htm", "text": b'{% include "parts/base.html" %}<div class="card">x</div>\n'},
            {"path": "molecules/parts/base.html", "text": b'<span>base</span>\n'},
            {"path": "components/base.css", "text": b'.card { color: black; }\n'},
        ],
        "fmt": None,
        "expect": [],
    },
    {
        "sources": [
            {"path": "pages/view.htm", "text": b'{% include "parts/base.html" %}<div class="card">x</div>\n'},
            {"path": "molecules/parts/base.html", "text": b'<span>base</span>\n'},
        ],
        "fmt": None,
        "expect": [("HC-REF003", "error")],
    },
    {
        "sources": [
            {"path": "widget.html", "text": b'<p class="ghostclass">The text .ghostclass is not a rule</p>\n'},
        ],
        "fmt": None,
        "expect": [("HC-REF003", "error")],
    },
    {
        "sources": [
            {"path": "notes.css", "text": b'.help::before { content: \'<span class="not-in-html">\'; }\n'},
        ],
        "fmt": None,
        "expect": [],
    },
    {"sources": [_SRC_DEAD_EXTENDS], "fmt": None, "expect": [("HC-REF002", "error")]},
    {"sources": [_SRC_DEAD_CLASS], "fmt": None, "expect": [("HC-REF003", "error")]},
    {"sources": [_SRC_FORMAT_CSS, _SRC_DEAD_HF], "fmt": _FMT, "expect": [("HC-REF004", "error")]},
    {"sources": [_SRC_FORMAT_CSS, _SRC_LIVE_HF], "fmt": _FMT, "expect": []},
    # Absence: every reference in the set resolves (and there are none to resolve).
    {"sources": [_SRC_CLEAN], "fmt": None, "expect": []},
]


def probe_check_references():
    """Resolve actions, templates, CSS classes, and formatting values across files."""
    try:
        from honest_check import check_references
    except ImportError as exc:
        return [f"cannot import check_references: {exc}"]

    bad = []
    for case in _CASES:
        got = check_references(sources=case["sources"], format_vocabulary=case["fmt"])
        for finding in got:
            if not finding["message"].strip():
                bad.append(f"reference finding has no explanation: {finding!r}")
            if finding["source_location"] not in {source["path"] for source in case["sources"]}:
                bad.append(f"reference finding has no source-file location: {finding!r}")
            if finding["context"] != "" or finding["fixable"] is not False:
                bad.append(f"unexpected context or automatic fix on reference finding: {finding!r}")
        if "action" in case:
            method, path = case["action"]
            for finding in got:
                if finding["rule_id"] == "HC-REF001" and (
                    method not in finding["message"] or path not in finding["message"]
                ):
                    bad.append(f"Expected the action method {method} and path {path!r}, got {finding!r}")
        pairs = [(d["rule_id"], d["severity"]) for d in got]
        if pairs != case["expect"]:
            bad.append(
                f"check_references({[s['path'] for s in case['sources']]!r}) -> "
                f"{pairs!r}, expected {case['expect']!r}"
            )
    return bad
