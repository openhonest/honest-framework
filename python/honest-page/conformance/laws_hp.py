"""honest-page conformance (spec section 11.2): the structural, bootstrap, and intake contracts checked
against the reference itself — the templates in python/templates and the server in python/app.py.

The reference is normative. Until now nothing ran it on commit: honest-check read it statically and found
every reference resolving, but no test exercised its behaviour, so the one artefact meant to show how a
host page is built was the one artefact not held to the framework's own gates. These laws close that.
"""

import re
import sys
from pathlib import Path

_PYTHON_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(_PYTHON_ROOT))

from jinja2 import Environment, FileSystemLoader

from app import extract_tokens

_TEMPLATES = _PYTHON_ROOT / "templates"

# The six surfaces, in the document order section 2.2 requires.
_SURFACES = [
    "honest-alerts-banners",
    "honest-header",
    "honest-alerts-toasts",
    "honest-main",
    "honest-footer",
    "honest-alerts-modal",
]


def _render(name, **context):
    return Environment(loader=FileSystemLoader(str(_TEMPLATES))).get_template(name).render(**context)


def _law_surfaces_in_document_order():
    """Section 11.2 structural: all six surface ids present, in the declared order."""
    html = _render("page.html", app_name="A", page_title="P", theme="auto")
    found = re.findall(r'id="(honest-[a-z-]+)"', html)
    return [] if found == _SURFACES else [f"surfaces must appear in the declared order: {found}"]


def _law_body_activates_domx():
    """Section 11.2 structural: the body carries hx-ext=domx and names the manifest, and the manifest is
    declared. Either attribute alone collects no state."""
    html = _render("page.html")
    bad = []
    if 'hx-ext="domx"' not in html or 'dx-manifest="appManifest"' not in html:
        bad.append("the body must carry hx-ext=domx and dx-manifest")
    if "const appManifest" not in html:
        bad.append("the page must declare appManifest")
    return bad


def _law_bootstrap_order():
    """Section 11.2 bootstrap: htmx precedes the SSE extension, which precedes domx, and the manifest
    follows domx. Loading out of order is undefined behaviour."""
    html = _render("page.html")
    scripts = [s.rsplit("/", 1)[-1] for s in re.findall(r'<script[^>]*src="([^"]+)"', html)]
    bad = [] if scripts == ["htmx.min.js", "sse.js", "domx.js"] else [f"bootstrap order wrong: {scripts}"]
    if html.index("const appManifest") < html.rindex("domx.js"):
        bad.append("the appManifest declaration must follow the domx script tag")
    return bad


def _law_sse_wiring():
    """Section 11.2 SSE: each notification surface connects to the stream with its own event type, and
    the banner and toast surfaces prepend while the modal replaces."""
    html = _render("page.html")
    bad = []
    if html.count('sse-connect="/api/alerts/stream"') != 3:
        bad.append("all three notification surfaces must connect to the alert stream")
    for event in ("alert:banner", "alert:toast", "alert:modal"):
        if f'sse-swap="{event}"' not in html:
            bad.append(f"a surface must subscribe to {event}")
    if html.count('hx-swap="afterbegin"') != 2 or 'hx-swap="innerHTML"' not in html:
        bad.append("banners and toasts prepend; the modal replaces")
    return bad


def _law_fragment_does_not_extend_base():
    """Section 10.2: a fragment route returns minimal HTML and does not extend base.html — no surfaces,
    no scripts, no manifest."""
    fragment = _render("search_results.html", rows=["alpha"])
    bad = []
    if "<script" in fragment or "honest-main" in fragment:
        bad.append("a fragment must not carry the page chrome")
    if "alpha" not in fragment:
        bad.append("a fragment must render its rows")
    return bad


def _law_intake_precedence():
    """Section 10.3: the three token sources merge, and _state wins over query, which wins over path.
    State the user established in the page is more specific than anything encoded in the URL."""
    bad = []
    if extract_tokens({"id": "7"}, {"page": "2"}, {"search": "hi"}) != {"id": "7", "page": "2", "search": "hi"}:
        bad.append("the three sources must merge")
    if extract_tokens({"q": "path"}, {"q": "query"}, {"q": "state"})["q"] != "state":
        bad.append("_state must win over a query parameter")
    if extract_tokens({"q": "path"}, {"q": "query"}, {})["q"] != "query":
        bad.append("a query parameter must win over a path parameter")
    if extract_tokens({"q": "path"}, {}, {})["q"] != "path":
        bad.append("a path parameter survives when nothing overrides it")
    if extract_tokens({}, {"page": "2"}, {}) != {"page": "2"}:
        bad.append("an absent _state leaves the query parameters alone")
    return bad


def _law_context_variables_default():
    """Section 6: every context variable is optional. A handler may pass none of them and the page still
    renders with the declared defaults."""
    html = _render("page.html")
    return [] if "Honest App" in html and "Page" in html else ["the base template must default every context variable"]


_LAWS = {
    "surfaces_in_document_order": _law_surfaces_in_document_order,
    "body_activates_domx": _law_body_activates_domx,
    "bootstrap_order": _law_bootstrap_order,
    "sse_wiring": _law_sse_wiring,
    "fragment_does_not_extend_base": _law_fragment_does_not_extend_base,
    "intake_precedence": _law_intake_precedence,
    "context_variables_default": _law_context_variables_default,
}


def run():
    violations = [(name, law()) for name, law in _LAWS.items()]
    failed = [(name, msgs) for name, msgs in violations if msgs]
    for name, msgs in failed:
        print(f"FAIL HP-law [{name}]: {msgs}")
    print(f"HP laws: {len(violations) - len(failed)} passed, {len(failed)} failed, {len(violations)} total")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(run())
