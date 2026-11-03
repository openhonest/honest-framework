"""honest-check the whole-program identity core (HC-A001, HC-A002), split from core.py so no module is a god-file (L1.17).

The per-rule logic nests here as data exactly as it did in core.py; the exact Diagnostic each
rule produces is pinned by the conformance suite (section 9.2), not by a separately declared
function."""

from honest_parse import language_of, line_col, parse, parse_source, walk
from honest_check.constants import _INNER_SCOPES


def check_auth(sources):
    """The pure whole-program core of the two identity rules HC-A001 and HC-A002
    (§HC-A001, §HC-A002), the whole-package counterpart of check_source for the two rules
    that turn on project-wide authentication-provider registration.

    sources is a list of SourceFile ({path, text}) — the project's code files. Both rules
    are whole-program, not per-file, because provider registration is project-wide: a
    provider registered in any one file governs every authorizing link across the whole
    project, so the whole set must be in view at once. A provider IS REGISTERED when some
    file calls register_auth_provider(...). An AUTHORIZING LINK is a top-level function
    decorated @link(authorizes=True). A link USES THE ACTOR when its own body references the
    name `actor`.

    HC-A001 (warning): when no file registers a provider and the set holds at least one
    authorizing link, one warning per authorizing link, at that link's def line — those links
    act on behalf of an actor no boundary validator resolves. HC-A002 (error): when a provider
    is registered, one error at each authorizing link whose body does not reference `actor` —
    a link declared authorizes=True that does not use the boundary-resolved actor is sourcing
    identity from forgeable request input. The provider-registered gate makes the two mutually
    exclusive over one set: HC-A001 only when no provider, HC-A002 only when one is registered.

    It opens no file and executes no application code — read_source did the reads — and raises
    nothing: a finding comes back as a Diagnostic. The per-rule logic nests here as data,
    exactly as check_source and check_roles hold their rules.
    """

    def call_arguments(call_node):
        """The (positional nodes, keyword name -> value node) of a call — the same read
        check_source's call_arguments does."""
        argument_list = call_node.child_by_field_name("arguments")
        positionals = []
        keywords = {}
        for child in argument_list.named_children:
            if child.type == "keyword_argument":
                name = child.child_by_field_name("name").text.decode("utf-8")
                keywords[name] = child.child_by_field_name("value")
            else:
                positionals.append(child)
        return positionals, keywords

    def called_name(call_node):
        """The name a call invokes — a bare identifier, or the final attribute of a dotted
        call — or None (§HC-P011's called_name idiom)."""
        function = call_node.child_by_field_name("function")
        if function.type == "identifier":
            return function.text.decode("utf-8")
        if function.type == "attribute":
            attr = function.child_by_field_name("attribute")
            return attr.text.decode("utf-8") if attr is not None else None
        return None

    def decorators_of(fdef):
        """The decorator nodes applied to a function — the `decorator` children of the
        enclosing `decorated_definition`, or [] for an undecorated function (§4.2's
        decorators_of idiom)."""
        parent = fdef.parent
        if parent is None or parent.type != "decorated_definition":
            return []
        return [child for child in parent.children if child.type == "decorator"]

    def link_authorizes(fdef):
        """True when a function carries a `@link(authorizes=True)` decorator — read the same
        way is_boundary_decorator reads `boundary`: from the decorator call's keyword
        arguments. A bare `@link` with no call, or `@link` without authorizes=True, is not an
        authorizing link."""
        for decorator in decorators_of(fdef):
            expr = decorator.named_children[0] if decorator.named_children else None
            if expr is None or expr.type != "call":
                continue
            function = expr.child_by_field_name("function")
            if function is None or function.type != "identifier":
                continue
            if function.text.decode("utf-8") != "link":
                continue
            _positionals, keywords = call_arguments(expr)
            value = keywords.get("authorizes")
            if value is not None and value.type == "true":
                return True
        return False

    def own_body(fdef):
        """The body descendants belonging to the function itself, not descending into a deeper
        nested def, lambda or decorated def — the same read check_source's own_body does."""
        body = fdef.child_by_field_name("body")
        found = []

        def gather(node):
            for child in node.named_children:
                if child.type in _INNER_SCOPES:
                    continue
                found.append(child)
                gather(child)

        gather(body)
        return found

    def uses_actor(fdef):
        """True when the function's own body references the name `actor` anywhere — the
        boundary-resolved identity flowing inward as data (§HC-A002)."""
        return any(
            node.type == "identifier" and node.text.decode("utf-8") == "actor"
            for node in own_body(fdef)
        )

    def facts_of(source_file):
        """One file's auth facts: whether it registers a provider, and the authorizing links
        it declares (each with its def-line location and whether it uses the actor). A file
        that does not parse contributes nothing — a parse failure is HC-SYN's finding.

        HC-A001 and HC-A002 read Python syntax: a register_auth_provider call and a
        @link(authorizes=True) decorator. Only a Python source can carry an auth fact, so a
        file under any other grammar contributes nothing. This is a language fact, not a
        defensive check: a Ruby or Elixir call node has no 'function' field, so reading one as
        if it were Python is a category error, not a case to guard against."""
        if language_of(source_file["path"]).get("ok") != "python":
            return {"registers_provider": False, "links": []}
        parsed = parse_source(source_file["text"].encode("utf-8"), source_file["path"])
        if "ok" not in parsed:
            return {"registers_provider": False, "links": []}
        root = parsed["ok"].root_node
        registers_provider = any(
            node.type == "call" and called_name(node) == "register_auth_provider"
            for node in walk(root)
        )
        links = []
        for top_node in root.named_children:
            if top_node.type == "function_definition":
                fdef = top_node
            elif top_node.type == "decorated_definition":
                definition = top_node.child_by_field_name("definition")
                fdef = (
                    definition
                    if definition is not None
                    and definition.type == "function_definition"
                    else None
                )
            else:
                fdef = None
            if fdef is None or not link_authorizes(fdef):
                continue
            line, col = line_col(fdef)
            links.append(
                {
                    "source_location": f"{source_file['path']}:{line}:{col}",
                    "uses_actor": uses_actor(fdef),
                }
            )
        return {"registers_provider": registers_provider, "links": links}

    facts = [facts_of(source) for source in sources]
    provider_registered = any(fact["registers_provider"] for fact in facts)
    authorizing_links = [link for fact in facts for link in fact["links"]]

    def hc_a001(link):
        return {
            "rule_id": "HC-A001",
            "severity": "warning",
            "message": "This link is declared to authorize an actor, but no AuthProvider is "
            "registered anywhere in the project, so the identity it acts under cannot be "
            "verified. Register a provider with register_auth_provider(...), or remove the "
            "actor dependency.",
            "source_location": link["source_location"],
            "context": "",
            "fixable": False,
        }

    def hc_a002(link):
        return {
            "rule_id": "HC-A002",
            "severity": "error",
            "message": "This link is declared authorizes=True but does not reference the "
            "boundary-resolved actor, so it sources identity from forgeable request input. "
            "Establish identity once at the boundary and pass it inward as the data named "
            "actor.",
            "source_location": link["source_location"],
            "context": "",
            "fixable": False,
        }

    # The provider-registered gate chooses which rule the set is judged by, so the two never
    # fire over the same set: HC-A001 covers the no-provider case, HC-A002 the with-provider.
    if not provider_registered:
        return [hc_a001(link) for link in authorizing_links]
    return [hc_a002(link) for link in authorizing_links if not link["uses_actor"]]
