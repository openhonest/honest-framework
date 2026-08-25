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
_THEME_CSS = _PYTHON_ROOT / "static" / "theme.css"

# Section 7.1, the whole required token set. Colour tokens are separated from the rest because the
# contract differs: section 7.2 requires every colour token to carry both values through light-dark(),
# and forbids it on the others, since light-dark() resolves to a <color> and wrapping a length in it is
# invalid CSS that silently fails to resolve.
_COLOR_TOKENS = [
    "--ht-color-bg-primary", "--ht-color-bg-secondary", "--ht-color-bg-surface",
    "--ht-color-text-primary", "--ht-color-text-secondary", "--ht-color-text-muted",
    "--ht-color-border", "--ht-color-border-strong",
    "--ht-color-accent", "--ht-color-accent-text",
    "--ht-color-success", "--ht-color-warning", "--ht-color-danger", "--ht-color-info",
]
_PLAIN_TOKENS = [
    "--ht-space-xs", "--ht-space-sm", "--ht-space-md", "--ht-space-lg", "--ht-space-xl", "--ht-space-2xl",
    "--ht-font-sans", "--ht-font-mono",
    "--ht-font-size-sm", "--ht-font-size-md", "--ht-font-size-lg", "--ht-font-size-xl", "--ht-font-size-2xl",
    "--ht-radius-sm", "--ht-radius-md", "--ht-radius-lg", "--ht-radius-pill",
]


def _root_block(css):
    """The declarations inside the first `:root { ... }` rule, as {token: value}. Pure."""
    # Comments come out first. Splitting on ";" leaves a preceding /* ... */ glued to the front of the
    # next declaration, so its name no longer starts with "--ht-" and the token reads as absent. That
    # dropped the first token of every category here and reported four present tokens as missing.
    match = re.search(r":root\s*\{([^}]*)\}", re.sub(r"/\*.*?\*/", "", css, flags=re.S))
    if not match:
        return {}
    return {name.strip(): value.strip()
            for name, _, value in (line.partition(":") for line in match.group(1).split(";"))
            if name.strip().startswith("--ht-")}


def _token_faults(css):
    """Section 11.2 CSS, as a pure decision over the stylesheet text.

    Checked here rather than in a browser because it is decidable from the source: the tokens are
    declared text, so a missing one is the same kind of fact as an undeclared name."""
    faults = []
    declared = _root_block(css)
    for token in _COLOR_TOKENS + _PLAIN_TOKENS:
        if token not in declared:
            faults.append(f"section 7.1 requires {token} on :root")
    for token in _COLOR_TOKENS:
        if token in declared and "light-dark(" not in declared[token]:
            faults.append(f"{token} is a colour token and must carry both values via light-dark()")
    for token in _PLAIN_TOKENS:
        if token in declared and "light-dark(" in declared[token]:
            faults.append(f"{token} is not a colour, and light-dark() around a length is invalid CSS")
    if not re.search(r":root\s*\{[^}]*color-scheme\s*:\s*light\s+dark", css):
        faults.append("section 7.2 requires `color-scheme: light dark` on :root, or light-dark() "
                      "does not resolve in all browsers")
    for forced in ('[data-theme="dark"]', '[data-theme="light"]'):
        if forced not in css:
            faults.append(f"section 7.3 requires a {forced} rule, so a choice can override the OS")
    return faults


def _law_html_element_and_theme_restoration():
    """Section 11.2 structural and bootstrap, the two facts that live on `<html>` and in `<head>`.

    `lang` is asserted because it is the one attribute a screen reader needs before anything renders,
    and it defaults rather than being required of every caller. The theme script must run in `<head>`,
    before `<body>` exists: run any later and the page paints in the OS theme first and then swaps,
    which is the flash the attribute exists to prevent. Order is the whole of that requirement, so the
    check is a position comparison and not the mere presence of the script."""
    faults = []
    html = _render("page.html", app_name="A", page_title="P", theme="auto")
    if not re.search(r"<html[^>]*\blang=", html):
        faults.append("section 11.2 structural: <html> must carry lang")

    head_end, body_start = html.find("</head>"), html.find("<body")
    restore = html.find("localStorage.getItem")
    if restore == -1:
        faults.append("section 11.2 bootstrap: the theme preference restoration script must be present")
    elif not (restore < head_end < body_start):
        faults.append("section 11.2 bootstrap: theme restoration must run inside <head>, before <body>, "
                      "or the page paints in the OS theme and then swaps")

    # Section 7.3 sets data-theme from script at load, not from the server into the markup, so the
    # attribute is absent from the served HTML by design and asserting it there would be asserting
    # something the spec does not say. What IS decidable from the source is that the server's choice
    # reaches the script that sets it: a template that renders the branch but drops the value leaves
    # an explicit theme with no way to take effect.
    for choice in ("dark", "light", "auto"):
        rendered = _render("page.html", app_name="A", page_title="P", theme=choice)
        script = rendered[:rendered.find("</head>")]
        if f'"{choice}"' not in script and f"'{choice}'" not in script:
            faults.append(f"theme {choice!r} must reach the restoration script, or it cannot take effect")
    return faults


def _law_request_is_the_first_context_variable():
    """Section 11.2 server: every TemplateResponse passes `request` first.

    Starlette reads the request out of the context by that key, and a template rendered without it
    raises only when something in the page happens to use `url_for`. So a route that omits it can
    serve correctly for as long as nobody adds a link, then break on an unrelated edit. Checked by
    reading the source rather than by calling the routes, because the fault is the absence of a key
    and absence is what a passing request cannot show."""
    source = (_PYTHON_ROOT / "app.py").read_text(encoding="utf-8")
    faults = []
    for call in re.finditer(r"TemplateResponse\(\s*\"([^\"]+)\"\s*,\s*\{\s*([^,:]*)", source):
        template, first_key = call.group(1), call.group(2).strip()
        if first_key != '"request"':
            faults.append(f"the context for {template} must pass \"request\" first, not {first_key or 'nothing'}")
    if not faults and "TemplateResponse(" not in source:
        faults.append("no TemplateResponse call found, so this law checked nothing")
    return faults


def _law_token_contract():
    """Section 11.2 CSS: every required token declared, colours through light-dark(), lengths not."""
    return _token_faults(_THEME_CSS.read_text(encoding="utf-8"))

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
    "html_element_and_theme_restoration": _law_html_element_and_theme_restoration,
    "request_is_the_first_context_variable": _law_request_is_the_first_context_variable,
    "token_contract": _law_token_contract,
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
