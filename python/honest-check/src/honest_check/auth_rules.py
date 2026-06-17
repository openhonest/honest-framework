"""Auth / HTTP-surface rules (spec §4.2): HC-A001, HC-P017.

HC-A001 (warning): links declare authorizes=True but no AuthProvider is
registered. HC-P017 (error): a function produces HTTP output without being a
declared @link with an emits vocabulary.

HC-A002 (authorizing guard must reference the provider's derivation_expression)
and HC-P015 (guard references a slot from a prior persist.read — cross-chain
TOCTOU) are NOT implemented here: both require honest-persist's guarded_mutation
/ guard-expression DSL, which is not yet rebuilt. They cannot be checked
statically against a guard DSL that does not exist; they land once honest-persist
provides the structured GuardExpression.
"""
from __future__ import annotations

from honest_check.declgraph import link_definitions
from honest_check.diagnostics import Diagnostic, diagnostic
from honest_check.parse import col_of, find_by_type, line_of, node_text


# --- HC-A001: no AuthProvider registered ----------------------------------


def check_hc_a001(root, src: bytes, path: str) -> list[Diagnostic]:
    links = link_definitions(root, src)
    authorizing = sorted(name for name, meta in links.items() if meta["authorizes"])
    if not authorizing:
        return []
    for call in find_by_type(root, "call"):
        func = call.child_by_field_name("function")
        if func is not None and node_text(func, src).split(".")[-1] == "register_auth_provider":
            return []   # a provider is registered
    loc = links[authorizing[0]]["node"]
    return [diagnostic(
        "HC-A001", "warning",
        f"Links declare authorizes=True but no AuthProvider is registered: "
        f"{authorizing}. Register a provider or set authorizes=False.",
        path, line_of(loc), col_of(loc))]


# --- HC-P017: HTTP output must be a declared serializer link ---------------

_HTTP_MARKERS = frozenset({
    "Response", "JSONResponse", "HTMLResponse", "PlainTextResponse",
    "RedirectResponse", "StreamingResponse", "render", "render_template",
})
_HTTP_ATTR_MARKERS = frozenset({"send", "json", "status", "render"})


def _produces_http(fn, src: bytes) -> bool:
    for call in find_by_type(fn, "call"):
        func = call.child_by_field_name("function")
        if func is None:
            continue
        if func.type == "identifier" and node_text(func, src) in _HTTP_MARKERS:
            return True
        if func.type == "attribute":
            attr = func.child_by_field_name("attribute")
            if attr is not None and node_text(attr, src) in _HTTP_ATTR_MARKERS:
                return True
    return False


def check_hc_p017(root, src: bytes, path: str) -> list[Diagnostic]:
    links = link_definitions(root, src)
    out: list[Diagnostic] = []
    for fn in find_by_type(root, "function_definition"):
        if not _produces_http(fn, src):
            continue
        name_node = fn.child_by_field_name("name")
        name = node_text(name_node, src) if name_node is not None else "<fn>"
        meta = links.get(name)
        if meta is None or not meta["emits"]:
            out.append(diagnostic(
                "HC-P017", "error",
                f"Function '{name}' produces HTTP output without being a declared "
                "@link with an emits vocabulary (status, content-type, body shape). "
                "Declare emits, or delegate to a serializer link.",
                path, line_of(fn), col_of(fn)))
    return out


AUTH_CHECKS = [
    check_hc_a001,
    check_hc_p017,
]
