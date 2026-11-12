"""The request path (honest-page-architecture.md §10): a typed request becomes a rendered page.

The pure core comes first. extract_tokens merges the three token sources into one manifest;
search_chain filters the rows the manifest asks for; page_context builds the server-side context
around a title. The orchestrators (build_manifest, run_search, build_home) each run one path and
delegate to one pure function. The doors (intake, index, search) are what the HTTP world calls: they
read the request and answer by their return. intake is the one async door — it awaits the request
body and the next handler — and index and search are plain, because constructing a template response
awaits nothing.
"""

import json
from urllib.parse import parse_qsl

from fastapi import Request
from honest_type import link


# §6 context defaults. Every context variable is optional: a handler may pass none of them and the
# page still renders. page_context builds the full set around the one value the caller gives, the
# title, so a handler names the title and takes the rest.
_CONTEXT_DEFAULTS = {
    "app_name": "Honest App",
    "lang": "en",
    "theme": "auto",
    "request_id": "",
}

# The rows the reference search chain filters (§10.2). The reference keeps the body a trivial demo:
# what matters is that the route map names the chain, so honest-check checks its first link against
# the fields the templates send.
_SEARCH_ROWS = ("alpha", "beta", "gamma")


def extract_tokens(path_params, query_params, state):
    """Merge the three token sources one request carries into one manifest (§10.3): path parameters,
    query parameters, and the `_state` domx collected from the DOM. Precedence is declared, not
    incidental: `_state` wins over query parameters, which win over path parameters, because state the
    user established in the page is more specific than anything encoded in the URL. Pure over the three
    already-extracted mappings."""
    return {**path_params, **query_params, **state}


def build_manifest(path_params, query_params, state):
    """Classify one request into one manifest (§10.3): hand the three sources to extract_tokens."""
    return extract_tokens(path_params, query_params, state)


def search_chain(manifest):
    """The chain the (GET, /search) route runs (§10.2): the classified manifest in, the rows out. Pure.
    The reference keeps the body trivial; the route map names it so honest-check can check this chain's
    first link against the fields the templates targeting /search send."""
    query = manifest.get("search", "")
    return [row for row in _SEARCH_ROWS if query in row]


def run_search(manifest):
    """Run the search chain over a manifest (§10.2): delegate to search_chain."""
    return search_chain(manifest)


def page_context(page_title):
    """Build the §6 server-side context around a title: the given title among the declared defaults.
    Pure. Every variable is optional downstream, so the base template defaults each in turn, but the
    reference renders them here so the context is one place a tool reads."""
    return {**_CONTEXT_DEFAULTS, "page_title": page_title}


def build_home(page_title):
    """Build the home page context (§10.2): delegate to page_context."""
    return page_context(page_title)


@link(boundary=True)
async def intake(request: Request, call_next):
    """The intake door (§10.3): classify what the request carries once, and hand the interior one
    manifest. Installed before every route, so each route reads `request.state.manifest` already
    resolved and no handler re-reads the request for its inputs. Async, because it awaits the request
    body and the next handler. The one HTTP read on the request path."""
    body = await request.body()
    state = json.loads(dict(parse_qsl(body.decode("utf-8"))).get("_state", "{}")) if body else {}
    request.state.manifest = build_manifest(dict(request.path_params), dict(request.query_params), state)
    response = await call_next(request)
    request_id = request.headers.get("X-Request-ID")
    if request_id is not None:
        response.headers["X-Request-ID"] = request_id
    return response


@link(boundary=True)
def index(request: Request):
    """The home door (§10.2): a full page. It hands the title to build_home and renders page.html,
    which extends base.html. The request goes to the template response first, and the §6 context
    follows. The template environment the factory mounted rides on the application."""
    context = build_home("Home")
    return request.app.state.templates.TemplateResponse(request, "page.html", context)


@link(boundary=True)
def search(request: Request):
    """The search door (§10.2): a fragment. It hands the manifest intake placed on the request to
    run_search and renders search_results.html, which does not extend base.html — it carries no
    surfaces, no scripts, no manifest, only the rows that changed."""
    rows = run_search(request.state.manifest)
    return request.app.state.templates.TemplateResponse(request, "search_results.html", {"rows": rows})
