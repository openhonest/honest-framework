"""HC002 first-link boundary check (honest-check spec section 4.2; honest-page sections 5, 9, 10.3).

The first link of a chain receives the manifest classify() builds at intake from the tokens the
templates targeting its route send — the closed input boundary (framework spec, "The input boundary is
closed"). This module derives that boundary vocabulary per route from the scanned templates and checks
each chain's first link's accepts against it. A first link declared a boundary is the intake itself and
is exempt. The inputs are already-parsed data — the route map, chains, links, and scanned templates —
so every function is pure; reading .py and template files stays at the caller's I/O boundary.
"""

from honest_check.declgraph import build_vocabulary_definitions, extract_chains, extract_links, extract_routes, resolve_aliases
from honest_check.diagnostics import diagnostic


def _path_params(path: str) -> frozenset:
    """The path parameters of a route pattern: the `{id}` segments of /items/{id} (honest-page 10.3)."""
    return frozenset(segment[1:-1] for segment in path.split("/") if len(segment) > 2 and segment[0] == "{" and segment[-1] == "}")


def _normalize_path(path: str) -> str:
    """A route path with every parameter or interpolation segment collapsed to `*`, so a template's
    concrete or interpolated target (/items/{{item.id}}) matches its route pattern (/items/{id})."""
    return "/".join("*" if "{" in segment else segment for segment in path.split("/"))


def route_boundary(method: str, path: str, sites: list, manifest_keys) -> dict:
    """The boundary vocabulary of a route: the fields every template site targeting that (method, path)
    sends, unioned with the route's path parameters and the application-state manifest keys. resolvable
    is False when any targeting site's path is not statically resolvable — an unknowable boundary."""
    fields = set(_path_params(path)) | set(manifest_keys)
    resolvable = True
    for site in sites:
        if site["method"] == method and _normalize_path(site["path"]) == _normalize_path(path):
            fields = fields | site["fields"]
            resolvable = resolvable and site["resolvable"]
    return {"fields": frozenset(fields), "resolvable": resolvable}


def check_boundary(routes: list, chains: list, links: dict, scanned_templates: list, path: str) -> list:
    """Check each chain named by a route: its first link's accepts must be suppliable by the boundary
    vocabulary derived from the templates targeting that route. A first link declared a boundary is the
    intake itself and is exempt. An unresolvable boundary — a template field or path that is not
    statically knowable — is itself an HC002 violation (honest-check spec section 4.2, line 461)."""
    sites = [site for scanned in scanned_templates for site in scanned["sites"]]
    manifest_keys = frozenset(key for scanned in scanned_templates for key in scanned["manifest_keys"])
    chain_route = {route["chain"]: route for route in routes}
    out = []
    for chain in chains:
        if not chain["links"]:
            continue
        first = links.get(chain["links"][0])
        route = chain_route.get(chain["name"])
        if first is None or first.get("boundary") or route is None:
            continue
        boundary = route_boundary(route["method"], route["path"], sites, manifest_keys)
        line, col = chain["location"]
        if not boundary["resolvable"]:
            out.append(diagnostic(
                "HC002", "error", path, line, col,
                f"Chain '{chain['name']}' runs route {route['method']} {route['path']}, but a template "
                "targeting it sends a field or path that is not statically resolvable, so its input "
                "boundary is unknowable. Make every hx-post/hx-get path and field name static.",
            ))
            continue
        missing = set(first["accepts"]) - boundary["fields"]
        if missing:
            out.append(diagnostic(
                "HC002", "error", path, line, col,
                f"First link '{chain['links'][0]}' of chain '{chain['name']}' accepts {sorted(missing)}, "
                f"which no template targeting {route['method']} {route['path']} can supply. Send the field "
                "from a template that targets this route, or drop it from the link's accepts.",
            ))
    return out


def check_references(routes: list, scanned_templates: list) -> list:
    """HC-REF001: every resolvable template action target resolves to a mounted route (honest-check spec
    section 4.2; framework spec, "Every reference resolves, or the gate stops"). This is the dual of
    HC002's route-to-template check — a template action pointing at a route nothing mounts is a dead
    reference, flagged at the site's own location. `routes` is the project-wide union of route patterns,
    so a target mounted in another file resolves; path parameters match through `_normalize_path`. An
    interpolated (unresolvable) target is HC002's unknowable-boundary domain and is not judged here. Pure
    over the already-parsed route map and scanned templates."""
    patterns = {(route["method"], _normalize_path(route["path"])) for route in routes}
    out = []
    for scanned in scanned_templates:
        for site in scanned["sites"]:
            if not site["resolvable"]:
                continue
            if (site["method"], _normalize_path(site["path"])) not in patterns:
                line, col = site["location"]
                out.append(diagnostic(
                    "HC-REF001", "error", scanned["path"], line, col,
                    f"Template action targets {site['method']} {site['path']}, which no route mounts. "
                    "Point it at a mounted route, or add the route.",
                ))
    return out


def check_template_references(resolvable: frozenset, scanned_templates: list) -> list:
    """HC-REF002: every literal `{% include %}`/`{% extends %}` target resolves to a template in the
    search path (honest-check spec section 4.2; framework spec, "Every reference resolves"). `resolvable`
    is the set of template paths relative to the search roots — the configured templates directory and
    its sibling `atoms/`/`molecules/` roots (honest-components) — so a target matches exactly as the
    loader searches. A dynamic target (a variable/expression, so `targets` is empty) is unresolvable and
    skipped, as HC-REF001 skips an interpolated route path; a conditional include contributes every literal
    branch, all of which must resolve. A literal target that no template provides is a dead reference,
    flagged at the tag. Pure over the already-parsed includes."""
    out = []
    for scanned in scanned_templates:
        for ref in scanned["includes"]:
            for target in ref["targets"]:
                if target not in resolvable:
                    line, col = ref["location"]
                    out.append(diagnostic(
                        "HC-REF002", "error", scanned["path"], line, col,
                        f"Template {ref['tag']} targets '{target}', which no template provides. "
                        "Add the template, or fix the path.",
                    ))
    return out


def check_class_references(defined_classes: frozenset, scanned_templates: list) -> list:
    """HC-REF003: every static class a template references resolves to a class the discovered component
    stylesheets define (honest-check spec section 4.2; framework spec, "Every reference resolves").
    `defined_classes` is the union of the class selectors across every stylesheet — a class defined for
    any component resolves, since the BEM namespace ownership is enforced at mount time, not here. A class
    that no stylesheet defines is a dead reference, flagged at the element. A class value carrying
    interpolation was already skipped whole at scan time. Pure over the already-parsed class references."""
    out = []
    for scanned in scanned_templates:
        for ref in scanned["class_refs"]:
            if ref["class"] not in defined_classes:
                line, col = ref["location"]
                out.append(diagnostic(
                    "HC-REF003", "error", scanned["path"], line, col,
                    f"Class '{ref['class']}' is defined by no stylesheet. Add the rule, or fix the class.",
                ))
    return out


def hf_vocabulary(manifest: dict) -> dict:
    """The checked-attribute -> allowed-values map HC-REF004 resolves against, built from honest-format's
    declared manifest (honest-check spec section 4.2): hf-format against the format names, hf-type against
    the input-type names, and each enumerated hf-*-format option against its own set. An attribute not in
    this map (a free value like hf-decimals or hf-currency) is not judged. Pure over the manifest data."""
    vocabulary = {"hf-format": frozenset(manifest["formats"]), "hf-type": frozenset(manifest["inputTypes"])}
    for attr, values in manifest["options"].items():
        vocabulary[attr] = frozenset(values)
    return vocabulary


def check_hf_references(vocabulary: dict, scanned_templates: list) -> list:
    """HC-REF004: every authored `hf-*` attribute value whose attribute names an enumerated vocabulary is
    a member of honest-format's declared vocabulary (honest-check spec section 4.2; framework spec, "Every
    reference resolves, or the gate stops"). `vocabulary` maps each checked attribute to its allowed
    values, read from honest-format's emitted manifest — declared, never inferred from source. An
    attribute carrying a free value (hf-decimals, hf-currency) is in no vocabulary and is not judged. A
    value naming no member — a typo'd hf-format="curency" that would render raw — is a dead reference,
    flagged at the element. Pure over the already-parsed hf-* references."""
    out = []
    for scanned in scanned_templates:
        for ref in scanned["hf_refs"]:
            allowed = vocabulary.get(ref["attr"])
            if allowed is not None and ref["value"] not in allowed:
                line, col = ref["location"]
                out.append(diagnostic(
                    "HC-REF004", "error", scanned["path"], line, col,
                    f'Attribute {ref["attr"]}="{ref["value"]}" names no member of honest-format\'s declared '
                    "vocabulary. Fix the value, or extend the vocabulary.",
                ))
    return out


def hc_vocabulary(manifest: dict) -> dict:
    """The declared component-behaviour vocabulary HC-REF004 resolves hc-* attributes against, built from
    honest-components' manifest (spec section 2.4): the set of behaviour attribute names (hc-<behaviour>)
    and the enumerated option values each option attribute allows. Declared as data, never scraped from
    the component modules. Pure over the manifest."""
    behaviours = frozenset(f"hc-{name}" for name in manifest["behaviors"])
    options = {attr: frozenset(values) for attr, values in manifest.get("options", {}).items()}
    return {"behaviours": behaviours, "options": options}


def check_hc_references(vocabulary: dict, scanned_templates: list) -> list:
    """HC-REF004 for components: every authored `hc-*` attribute resolves against honest-components'
    declared vocabulary (spec section 2.4; framework spec, "Every reference resolves, or the gate stops").
    An option attribute's value must be an enumerated member; any other hc-* attribute's name must be a
    declared behaviour. A typo'd hc-swich names no module and an option value naming no member — either
    would be silently inert in the browser — is a dead reference, flagged at the element. Pure over the
    already-parsed hc-* references."""
    out = []
    behaviours = vocabulary["behaviours"]
    options = vocabulary["options"]
    for scanned in scanned_templates:
        for ref in scanned["hc_refs"]:
            attr = ref["attr"]
            if attr in options:
                if ref["value"] is not None and ref["value"] not in options[attr]:
                    line, col = ref["location"]
                    out.append(diagnostic(
                        "HC-REF004", "error", scanned["path"], line, col,
                        f'Attribute {attr}="{ref["value"]}" names no member of honest-components\' declared '
                        "option vocabulary. Fix the value, or extend the vocabulary.",
                    ))
            elif attr not in behaviours:
                line, col = ref["location"]
                out.append(diagnostic(
                    "HC-REF004", "error", scanned["path"], line, col,
                    f"Attribute {attr} names no honest-components behaviour in the declared vocabulary. Fix "
                    "the name, or extend the vocabulary.",
                ))
    return out


def boundary_diagnostics(root, source: bytes, path: str, scanned_templates: list) -> list:
    """Run the first-link boundary check on one parsed source file given the scanned templates: read its
    route map, chains, and links, then check_boundary against the templates. A file that declares no
    ROUTES has no route boundary to derive, so it yields nothing. This is the seam the CLI calls once
    the template directory has been scanned at its I/O boundary."""
    routes = extract_routes(root, source)
    if not routes:
        return []
    aliases = resolve_aliases(root, source)
    vocab_defs = build_vocabulary_definitions(root, source, aliases)
    links = extract_links(root, source, aliases, vocab_defs)
    chains = extract_chains(root, source, aliases)
    return check_boundary(routes, chains, links, scanned_templates, path)
