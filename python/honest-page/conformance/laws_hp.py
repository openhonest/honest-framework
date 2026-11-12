"""honest-page conformance (spec section 11.2): the structural, bootstrap, intake, factory, and hook
contracts checked against the built package.

The reference used to be python/app.py and loose templates that nothing ran on commit. honest-page is
now one installable package: the templates and the token stylesheet ship inside it (read_bundle names
them), create_app is the composition root, and these laws exercise the real application end to end —
they build it, drive requests through the intake middleware and the route handlers over ASGI, and read
the rendered bytes. The value-pinned functions (extract_tokens, surface_slot, page_context) also carry
value cases in suite.json, checked centrally by value-check.py.
"""

import asyncio
import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from honest_page import (
    assembly,
    attach_stream,
    create_app,
    extract_tokens,
    read_bundle,
    route_table,
    surface_slot,
)
from honest_page.hook import _REGISTERED_SOURCES

# The laws read the bundle the factory ships, so a template or stylesheet that moves out of the package
# fails here rather than passing against a copy left behind in the tree.
_BUNDLE = read_bundle()
_TEMPLATES = Path(_BUNDLE["template_dir"])
_THEME_CSS = Path(_BUNDLE["static_dir"]) / "theme.css"

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


def _render(name, **context):
    return Environment(loader=FileSystemLoader(str(_TEMPLATES))).get_template(name).render(**context)


# The six surfaces, in the document order section 2.2 requires.
_SURFACES = [
    "honest-alerts-banners",
    "honest-header",
    "honest-alerts-toasts",
    "honest-main",
    "honest-footer",
    "honest-alerts-modal",
]


async def _drive(app, method, path, query=b"", body=b"", headers=None):
    """Run one request through the real application over ASGI: the intake middleware, the router, and
    the handler, exactly as an ASGI server would. Returns (status, headers, body). This is how the
    laws exercise the doors against the templates the package ships, without a running server."""
    scope = {
        "type": "http", "http_version": "1.1", "method": method, "path": path,
        "raw_path": path.encode(), "query_string": query, "headers": headers or [],
        "scheme": "http", "server": ("testserver", 80), "client": ("testclient", 1),
        "root_path": "", "app": app,
    }
    pending = [{"type": "http.request", "body": body, "more_body": False}]
    captured = {"status": None, "headers": [], "body": b""}

    async def receive():
        return pending.pop(0) if pending else {"type": "http.disconnect"}

    async def send(message):
        if message["type"] == "http.response.start":
            captured["status"] = message["status"]
            captured["headers"] = message["headers"]
        elif message["type"] == "http.response.body":
            captured["body"] += message.get("body", b"")

    await app(scope, receive, send)
    return captured


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

    for choice in ("dark", "light", "auto"):
        rendered = _render("page.html", app_name="A", page_title="P", theme=choice)
        script = rendered[:rendered.find("</head>")]
        if f'"{choice}"' not in script and f"'{choice}'" not in script:
            faults.append(f"theme {choice!r} must reach the restoration script, or it cannot take effect")
    return faults


def _law_token_contract():
    """Section 11.2 CSS: every required token declared, colours through light-dark(), lengths not."""
    return _token_faults(_THEME_CSS.read_text(encoding="utf-8"))


def _law_application_factory():
    """Section 10.4: create_app builds one application from declared data. The route map is data a tool
    reads without running the factory, the assembly packs the shipped bundle, and the built application
    mounts static, carries the template environment, and registers one handler per route-map entry."""
    bad = []
    routes = route_table()
    if [(e["method"], e["path"]) for e in routes] != [("GET", "/"), ("GET", "/search")]:
        bad.append("route_table must declare GET / and GET /search as data")
    if {e["chain"] for e in routes} != {"index", "search"}:
        bad.append("each route entry must name the handler that path runs")

    plan = assembly(_BUNDLE, routes)
    if plan["routes"] is not routes or plan["template_dir"] != _BUNDLE["template_dir"] or plan["static_dir"] != _BUNDLE["static_dir"]:
        bad.append("assembly must pack the bundle's directories and the route table into the plan")
    if not Path(plan["template_dir"]).is_dir() or not Path(plan["static_dir"]).is_dir():
        bad.append("the shipped bundle must point at real template and static directories")

    app = create_app()
    paths = {getattr(route, "path", None) for route in app.routes}
    for required in ("/", "/search", "/static"):
        if required not in paths:
            bad.append(f"the built application must serve {required}")
    if not hasattr(app.state, "templates"):
        bad.append("the factory must register the template environment on the application")
    return bad


def _law_request_path_renders():
    """Section 10.2, 10.3: the built application answers requests. GET / is a full page carrying every
    surface and the bootstrap scripts; GET /search is a fragment carrying only the filtered rows and no
    page chrome. The intake middleware runs ahead of both — it classifies _state from the body into the
    manifest, and it echoes X-Request-ID back when the request carries one."""
    app = create_app()

    async def run():
        bad = []
        # GET / with no body and no request id: intake takes the empty-body and no-id paths; index
        # renders the full page from its defaults.
        home = await _drive(app, "GET", "/")
        home_html = home["body"].decode()
        if home["status"] != 200:
            bad.append(f"GET / must answer 200, got {home['status']}")
        for marker in (f'id="{surface}"' for surface in _SURFACES):
            if marker not in home_html:
                bad.append(f"the home page must render {marker}")
        if "Honest App" not in home_html or 'sse-connect="/api/alerts/stream"' not in home_html:
            bad.append("the home page must render the chrome and the alert-stream wiring")

        # GET / carrying a _state body and an X-Request-ID: intake takes the body-present and id-present
        # paths. The id must come back on the response.
        echoed = await _drive(
            app, "GET", "/",
            body=b'_state=%7B%22k%22%3A%22v%22%7D',
            headers=[(b"x-request-id", b"req-7")],
        )
        if not any(key == b"x-request-id" and value == b"req-7" for key, value in echoed["headers"]):
            bad.append("intake must echo X-Request-ID back onto the response")

        # GET /search with _state carrying the search term: the fragment carries only the matching row,
        # and none of the page chrome.
        fragment = await _drive(app, "GET", "/search", body=b'_state=%7B%22search%22%3A%22al%22%7D')
        fragment_html = fragment["body"].decode()
        if fragment["status"] != 200:
            bad.append(f"GET /search must answer 200, got {fragment['status']}")
        if "alpha" not in fragment_html or "beta" in fragment_html or "gamma" in fragment_html:
            bad.append("the search fragment must carry only the rows matching the term")
        if "<script" in fragment_html or "honest-main" in fragment_html:
            bad.append("the search fragment must not carry the page chrome")
        return bad

    return asyncio.run(run())


def _law_surface_slot_resolution():
    """Section 2.1, 4.5: surface_slot resolves a surface id against the registry to the slot its markup
    lands in, and answers nothing for an id that is not a declared surface."""
    bad = []
    expected = {
        "honest-alerts-banners": "div",
        "honest-header": "header",
        "honest-alerts-toasts": "div",
        "honest-main": "main",
        "honest-footer": "footer",
        "honest-alerts-modal": "div",
    }
    for surface_id, slot in expected.items():
        if surface_slot(surface_id) != slot:
            bad.append(f"surface_slot({surface_id!r}) must resolve to {slot!r}")
    if surface_slot("not-a-surface") is not None:
        bad.append("surface_slot must answer nothing for an id that is not a declared surface")
    return bad


def _law_sse_hook_registers_a_source():
    """Section 4.5: a custom module registers its own SSE source against one declared surface through
    attach_stream. honest-page resolves the surface to its slot and commits the source on the stream's
    source table, without naming the registering module."""
    bad = []

    def custom_source():
        return "a custom event stream"

    before = len(_REGISTERED_SOURCES)
    registration = attach_stream("honest-alerts-banners", "alert:banner", custom_source)
    if registration["slot"] != "div":
        bad.append("attach_stream must resolve the surface to its slot before registering")
    if registration["event_type"] != "alert:banner" or registration["source"] is not custom_source:
        bad.append("the registration must carry the event type and the source the module named")
    if len(_REGISTERED_SOURCES) != before + 1 or _REGISTERED_SOURCES[-1] is not registration:
        bad.append("register_source must commit the registration onto the stream's source table")
    return bad


_LAWS = {
    "surfaces_in_document_order": _law_surfaces_in_document_order,
    "body_activates_domx": _law_body_activates_domx,
    "bootstrap_order": _law_bootstrap_order,
    "sse_wiring": _law_sse_wiring,
    "fragment_does_not_extend_base": _law_fragment_does_not_extend_base,
    "intake_precedence": _law_intake_precedence,
    "context_variables_default": _law_context_variables_default,
    "html_element_and_theme_restoration": _law_html_element_and_theme_restoration,
    "token_contract": _law_token_contract,
    "application_factory": _law_application_factory,
    "request_path_renders": _law_request_path_renders,
    "surface_slot_resolution": _law_surface_slot_resolution,
    "sse_hook_registers_a_source": _law_sse_hook_registers_a_source,
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
