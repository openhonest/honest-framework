"""Evaluate the construction and per-file rules, then apply suppression."""

import itertools

from honest_parse import language_of, walk

from ._util import choose, pick, read_or
from .analysis import (
    body_has_call,
    canonical_body,
    is_empty_default,
    link_is_impure,
    module_mutable_globals,
    predicate_is_risky,
    watched,
)
from .bindings import (
    binding_keys,
    binding_slots,
    construction_maps,
    feature_state_flag,
    features_vocabulary,
    module_dict_literals,
    vocabulary_binding_pairs,
    vocabulary_types,
)
from .decorators import (
    _keyword_value,
    decorator_target,
    decorators_of,
    has_decorator,
    in_non_boundary_function,
    is_boundary_decorator,
    link_declares_emits,
)
from .diagnostics import diagnostic, file_diagnostic
from .nodes import (
    _field,
    _text,
    bare_or_final_name,
    call_arguments,
    called_name,
    canonical_name,
    is_main_guard,
    literal_string,
    mutated_names,
    nonlocal_names,
    own_body,
    string_members,
    underscore_self_name,
    within_class_init,
)

from .io_rules import _IO_WATCH, _call_target_watched, _hc_p004

from .suppression import (
    _diag_line, _directive_record, _directives, _is_directive,
    _matches, _resolve_one, _suppression_findings, apply_suppression,
)

_CALL_TYPES = {"call", "call_expression"}


def _calls_named(ctx, name):
    calls = filter(lambda n: n.type == "call", ctx["nodes"])
    return filter(lambda c: canonical_name(ctx, c) == name, calls)


def _language(ctx):
    return read_or(language_of(ctx["path"]), "ok", "python")


# ---- construction-time rules (§4.1) ----------------------------------------


def _hc007(ctx):
    chains = _calls_named(ctx, "chain")
    empty = filter(lambda c: len(call_arguments(ctx, c)["positionals"]) == 0, chains)
    return [
        diagnostic(ctx, "HC007", "error", "empty chain: chain() constructed with no links", c)
        for c in empty
    ]


def _set_members(base):
    sets = filter(lambda bt: bt["kind"] == "set", base.values())
    return [bt["members"] for bt in sets]


def _hc003(ctx):
    out = []
    for vocab in _calls_named(ctx, "vocabulary"):
        sets = _set_members(vocabulary_types(ctx, vocab)["base_types"])
        overlap = any(len(a & b) > 0 for a, b in itertools.combinations(sets, 2))
        out.extend(
            pick(
                overlap,
                lambda: [
                    diagnostic(ctx, "HC003", "error", "recognizer overlap: two Set recognizers share a value", vocab)
                ],
                lambda: [],
            )
        )
    return out


def _hc011(ctx):
    out = []
    for vocab in _calls_named(ctx, "vocabulary"):
        base = vocabulary_types(ctx, vocab)["base_types"]
        predicates = filter(lambda bt: bt["kind"] == "predicate", base.values())
        out.extend(
            [
                diagnostic(ctx, "HC011", "info", "predicate recognizer cannot be sampled statically; see the runtime check", vocab)
                for _ in predicates
            ]
        )
    return out


def _dict_pairs(node):
    return pick(
        node is None or node.type != "dictionary",
        lambda: [],
        lambda: list(filter(lambda c: c.type == "pair", node.named_children)),
    )


def _string_value(node):
    return pick(
        node is not None and node.type == "string",
        lambda: literal_string(node),
        lambda: None,
    )


def _vocab_members(ctx, vocab_node):
    base = pick(vocab_node is None, lambda: {}, lambda: vocabulary_types(ctx, vocab_node)["base_types"])
    members = set()
    for bt in filter(lambda bt: bt["kind"] == "set", base.values()):
        members.update(bt["members"])
    return members


def _tuple_strings(node):
    return pick(
        node is None or node.type != "tuple",
        lambda: [],
        lambda: [literal_string(c) for c in filter(lambda c: c.type == "string", node.named_children)],
    )


def _at(items, index):
    return pick(len(items) > index, lambda: items[index], lambda: None)


def _transitions(ctx, dict_node):
    out = []
    for pair in _dict_pairs(dict_node):
        parts = _tuple_strings(_field(pair, "key"))
        out.append(
            {"from": _at(parts, 0), "event": _at(parts, 1), "to": _string_value(_field(pair, "value"))}
        )
    return out


def _sm_reachable(initial, transitions):
    graph = {}
    for transition in transitions:
        graph.setdefault(transition["from"], set()).add(transition["to"])
    seen = {initial}
    frontier = [initial]
    while frontier:
        node = frontier.pop()
        fresh = read_or(graph, node, set()) - seen
        seen |= fresh
        frontier.extend(fresh)
    return seen


def _terminal_states(ctx, node):
    return pick(node is None, lambda: set(), lambda: set(string_members(ctx, node)))


def _sm03(ctx, machine, states, initial, reachable):
    unreachable = list(filter(lambda s: s not in reachable and s != initial, states))
    return [
        diagnostic(ctx, "HC-SM03", "warning", "state unreachable from the initial state", machine)
        for _ in unreachable
    ]


def _sm04(ctx, machine, states, transitions, terminal, reachable):
    # A reachable state with no outgoing transition that is not declared terminal is a
    # dead state (§HC-SM04). It is gated on reachability so an unreachable state is
    # HC-SM03's one finding, not two; terminal states are sinks by declaration, so they
    # are exempt. HC-SM04's `terminal` is read off the state_machine(...) call.
    dead = list(filter(
        lambda s: s in reachable and not any(t["from"] == s for t in transitions) and s not in terminal,
        states,
    ))
    return [
        diagnostic(ctx, "HC-SM04", "warning", "state has no outgoing transition and is not declared terminal", machine)
        for _ in dead
    ]


def _state_machine_rules(ctx, machine):
    keywords = call_arguments(ctx, machine)["keywords"]
    states = _vocab_members(ctx, read_or(keywords, "states", None))
    events = _vocab_members(ctx, read_or(keywords, "events", None))
    initial = _string_value(read_or(keywords, "initial", None))
    transitions = _transitions(ctx, read_or(keywords, "transitions", None))
    terminal = _terminal_states(ctx, read_or(keywords, "terminal", None))
    bad_state = any(t["from"] not in states or t["to"] not in states for t in transitions)
    bad_event = any(t["event"] not in events for t in transitions)
    bad_initial = bool(initial is not None and initial not in states)
    # HC-SM03 and HC-SM04 are reachability-and-shape findings that only read a sound
    # machine: a bad transition (HC-SM01), a bad event (HC-SM02) or a bad initial state
    # (HC-SM05) is the structural fault, and echoing it as a storm of unreachable or
    # dead states would bury the one finding that names the cause.
    sound = not bad_state and not bad_event and not bad_initial
    reachable = pick(sound, lambda: _sm_reachable(initial, transitions), lambda: set())
    return (
        pick(bad_state, lambda: [diagnostic(ctx, "HC-SM01", "error", "transition-table state not in the states vocabulary", machine)], lambda: [])
        + pick(bad_event, lambda: [diagnostic(ctx, "HC-SM02", "error", "transition-table event not in the events vocabulary", machine)], lambda: [])
        + pick(bad_initial, lambda: [diagnostic(ctx, "HC-SM05", "error", "initial state not in the states vocabulary", machine)], lambda: [])
        + pick(sound, lambda: _sm03(ctx, machine, states, initial, reachable), lambda: [])
        + pick(sound, lambda: _sm04(ctx, machine, states, transitions, terminal, reachable), lambda: [])
    )


def _hc_state_machines(ctx):
    out = []
    for machine in _calls_named(ctx, "state_machine"):
        out.extend(_state_machine_rules(ctx, machine))
    return out


# ---- vocabulary/binding pairing rules (§HC004, §HC005, §HC-P013) -------------

_ROUTING_KEYS = {"db_id", "tenant_id", "credential"}


def _composed_bases(surface):
    bases = set()
    for composed in surface["composed"]:
        bases |= composed["requires_bases"] | composed["captures_bases"]
    return bases


def _hc004(ctx):
    out = []
    for vocabs, binding in vocabulary_binding_pairs(ctx):
        bound = binding_keys(ctx, binding)
        for vocab in vocabs:
            surface = vocabulary_types(ctx, vocab)
            composed = _composed_bases(surface)
            dead = filter(lambda n: n not in bound and n not in composed, surface["base_names"])
            out.extend(
                diagnostic(ctx, "HC004", "warning", "vocabulary type defined but never bound or composed", vocab)
                for _ in dead
            )
    return out


def _hc_p013(ctx):
    out = []
    for vocabs, binding in vocabulary_binding_pairs(ctx):
        base = {}
        defining = {}
        for vocab in vocabs:
            types = vocabulary_types(ctx, vocab)["base_types"]
            base.update(types)
            for name in types:
                defining.setdefault(name, vocab)
        for type_name, slot in binding_slots(ctx, binding).items():
            info = read_or(base, type_name, {"kind": None})
            fire = slot in _ROUTING_KEYS and info["kind"] == "predicate" and type_name in defining
            out.extend(
                pick(
                    fire,
                    lambda: [diagnostic(ctx, "HC-P013", "error", "routing key bound to a predicate recognizer instead of a bounded Set", defining[type_name])],
                    lambda: [],
                )
            )
    return out


# ---- link rules (§HC008, §HC010) --------------------------------------------

_HC008_WATCH = {
    "python": {
        # Filesystem
        "open", "pathlib.Path.open", "pathlib.Path.read_text", "pathlib.Path.write_text",
        "pathlib.Path.read_bytes", "pathlib.Path.write_bytes", "os.open", "os.read",
        "os.write", "os.remove", "os.rename", "os.mkdir", "os.rmdir", "os.listdir",
        "os.walk", "shutil.copy", "shutil.move", "shutil.rmtree", "tempfile.*",
        "mmap.mmap",
        # Process / shell
        "subprocess.run", "subprocess.Popen", "subprocess.call", "subprocess.check_output",
        "os.system", "os.popen", "os.execvp", "os.spawn*", "os.fork",
        # Network
        "socket.*", "http.client.*", "urllib.request.*", "urllib.urlopen",
        "requests.*", "httpx.*", "aiohttp.*", "urllib3.*", "smtplib.*",
        "ftplib.*", "poplib.*", "imaplib.*", "telnetlib.*", "ssl.*",
        # Process state / stdio
        "print", "input", "sys.stdout.write", "sys.stderr.write",
        "sys.stdin.read", "logging.*",
        # Database drivers
        "psycopg2.connect", "psycopg.connect", "asyncpg.connect", "sqlite3.connect",
        "aiosqlite.connect", "pymongo.MongoClient", "redis.Redis",
        # Randomness
        "random.*", "secrets.*", "uuid.uuid1", "uuid.uuid3", "uuid.uuid4", "uuid.uuid5",
        "os.urandom",
        # Time
        "time.time", "time.time_ns", "time.monotonic", "time.perf_counter",
        "time.process_time", "time.sleep",
        "datetime.datetime.now", "datetime.datetime.utcnow", "datetime.datetime.today",
        "datetime.date.today",
        # Environment / process
        "os.environ", "os.getenv", "os.getlogin", "os.getpid", "os.getppid",
        "os.getcwd", "os.uname", "os.environ.get", "getpass.getpass", "getpass.getuser",
        "platform.*", "sys.argv", "sys.version", "sys.path", "__file__", "__name__",
        # Thread / process state
        "threading.current_thread", "threading.get_ident", "threading.active_count",
        "multiprocessing.current_process", "multiprocessing.cpu_count",
        "asyncio.get_event_loop", "asyncio.current_task",
        # Object identity
        "id",
    },
    "javascript": {
        # Filesystem / Node
        "fs.*", "fsp.*",
        # Network
        "fetch", "XMLHttpRequest", "http.request", "https.request",
        "WebSocket", "EventSource", "navigator.sendBeacon",
        # Storage (browser)
        "localStorage.*", "sessionStorage.*", "indexedDB.*", "caches.*",
        # Process / stdio
        "process.stdout.write", "process.stderr.write", "process.stdin.*",
        "console.log", "console.error", "console.warn", "console.info", "console.debug",
        # Database drivers
        "pg.*", "mongodb.*", "redis.*", "mysql.*", "sqlite3.*",
        # Randomness
        "Math.random", "crypto.getRandomValues", "crypto.randomUUID",
        # Time
        "Date.now", "performance.now",
        # Environment / process
        "process.env", "process.pid", "process.cwd", "process.argv",
        "process.platform", "process.version", "document.cookie",
    },
}


def _is_boundary_link(ctx, fdef):
    return any(is_boundary_decorator(ctx, d) for d in decorators_of(ctx, fdef))


# inherits: hd=python/honest-check/honest-check.hd::_links -> feature=specs/features/honest-check.feature::_links selects direct top-level JavaScript link callbacks -> test=python/honest-check/conformance/probe_links_javascript_wrappers.py::probe_links_javascript_wrappers
# hd: _links
def _links(ctx):
    """Select non-boundary Python links and direct JavaScript inline callbacks."""
    match _language(ctx):
        case "javascript":
            declarations = filter(
                lambda node: node.type == "lexical_declaration" and node.children[0].type == "const",
                ctx["root"].named_children,
            )
            bindings = (binding for declaration in declarations for binding in declaration.named_children)
            values = (_field(binding, "value") for binding in bindings)
            calls = filter(lambda node: node is not None and node.type == "call_expression", values)
            callbacks = []
            for call in calls:
                head = _field(call, "function")
                arguments_node = _field(call, "arguments")
                members = arguments_node and arguments_node.named_children or ()
                arguments = list(filter(lambda node: node.type != "comment", members))
                direct = head is not None and head.type == "identifier" and head.text == b"link" and not any(
                    child.type == "optional_chain" for child in call.named_children
                )
                inline = (
                    arguments_node is not None and arguments_node.type == "arguments"
                    and len(arguments) == 2 and arguments[0].type == "object"
                    and arguments[1].type in {"arrow_function", "function_expression"}
                )
                match direct and inline:
                    case False:
                        continue
                keys = (
                    _field(member, "key") or member
                    for member in filter(lambda node: node.type != "comment", arguments[0].named_children)
                )
                readable = all(
                    key.type in {"property_identifier", "shorthand_property_identifier", "number", "string"}
                    and not any(child.type == "escape_sequence" for child in key.named_children)
                    and key.text not in {b"boundary", b"'boundary'", b'"boundary"'}
                    for key in keys
                )
                callbacks.extend(pick(readable, lambda: [arguments[1]], list))
            return callbacks
        case _:
            return list(filter(
                lambda f: has_decorator(ctx, f, "link") and not _is_boundary_link(ctx, f),
                _top_level_functions(ctx),
            ))


def _hc008(ctx):
    watch = read_or(_HC008_WATCH, _language(ctx), set())
    mutable = module_mutable_globals(ctx)
    firing = filter(lambda f: link_is_impure(ctx, f, watch, mutable), _links(ctx))
    return [
        diagnostic(ctx, "HC008", "warning", "link may be impure: it calls I/O or reads a mutable global without boundary=True", f)
        for f in firing
    ]


def _link_decorators(ctx, fdef):
    return list(filter(lambda d: decorator_target(d) == "link", decorators_of(ctx, fdef)))


def _vocab_base_names(ctx, text, construction):
    node = read_or(construction, text, None)
    return pick(node is None, lambda: set(), lambda: vocabulary_types(ctx, node)["base_names"])


def _bind_reverse(ctx, text, construction):
    node = pick(text is None, lambda: None, lambda: read_or(construction, text, None))
    slots = pick(node is None, lambda: {}, lambda: binding_slots(ctx, node))
    return {slot: type_name for type_name, slot in slots.items()}


def _param_identifier(fdef):
    params = _field(fdef, "parameters")
    children = pick(params is None, lambda: [], lambda: list(params.named_children))
    first = pick(len(children) == 0, lambda: None, lambda: children[0])
    return pick(first is not None and first.type == "identifier", lambda: first.text.decode("utf-8"), lambda: None)


def _subscript_string_key(node):
    others = list(filter(lambda c: c != _field(node, "value"), node.named_children))
    key = pick(len(others) == 0, lambda: None, lambda: others[0])
    return pick(key is not None and key.type == "string", lambda: literal_string(key), lambda: None)


def _produced_keys(ctx, fdef, manifest_param):
    keys = set()
    body = own_body(fdef)
    assigns = filter(lambda n: n.type == "assignment", body)
    for assignment in assigns:
        left = _field(assignment, "left")
        hit = bool(
            left is not None
            and left.type == "subscript"
            and _text(_field(left, "value")) == manifest_param
        )
        keys.update(pick(hit, lambda: {_subscript_string_key(left)}, lambda: set()))
    returns = filter(lambda n: n.type == "return_statement", body)
    for statement in returns:
        value = next(filter(lambda c: c.type == "dictionary", statement.named_children), None)
        keys.update(pick(value is None, lambda: set(), lambda: _dict_literal_keys(value)))
    return keys - {None}


def _dict_literal_keys(node):
    pairs = filter(lambda c: c.type == "pair", node.named_children)
    strings = filter(lambda p: _field(p, "key").type == "string", pairs)
    return set(literal_string(_field(p, "key")) for p in strings)


def _hc010(ctx):
    construction = construction_maps(ctx)
    out = []
    for fdef in _top_level_functions(ctx):
        for decorator in _link_decorators(ctx, fdef):
            emits_text = _keyword_value(decorator, "emits")
            emits = _vocab_base_names(ctx, emits_text, construction)
            accepts = _vocab_base_names(ctx, _keyword_value(decorator, "accepts"), construction)
            reverse = _bind_reverse(ctx, _keyword_value(decorator, "bind"), construction)
            produced = set(read_or(reverse, key, None) for key in _produced_keys(ctx, fdef, _param_identifier(fdef)))
            phantom = emits - produced - accepts
            fire = emits_text is not None and len(phantom) > 0
            out.extend(
                pick(
                    fire,
                    lambda: [diagnostic(ctx, "HC010", "warning", "link declares an emission it never produces", fdef)],
                    lambda: [],
                )
            )
    return out


# inherits: hd=python/honest-check/honest-check.hd::check_construction -> feature=specs/features/honest-check.feature::check_construction leaves HC010 to the per-file rule group -> test=python/honest-check/conformance/probe_check_construction_hc010_per_file.py::probe_check_construction_hc010_per_file
# inherits: hd=python/honest-check/honest-check.hd::check_construction -> feature=specs/features/honest-check.feature::check_construction leaves HC005 to the per-file rule group -> test=python/honest-check/conformance/probe_check_construction_hc005_per_file.py::probe_check_construction_hc005_per_file
# inherits: hd=python/honest-check/honest-check.hd::check_construction -> feature=specs/features/honest-check.feature::check_construction -> test=python/honest-check/conformance/probe_check_construction.py::probe_check_construction
# inherits: hd=python/honest-check/honest-check.hd::check_construction -> feature=specs/features/honest-check.feature::check_construction checks optional capture base names with HC006 -> test=python/honest-check/conformance/probe_check_construction_optional_capture.py::probe_check_construction_optional_capture
# inherits: hd=python/honest-check/honest-check.hd::check_construction -> feature=specs/features/honest-check.feature::check_construction anchors JavaScript HC008 warnings to inline callbacks -> test=python/honest-check/conformance/probe_check_construction_javascript_hc008.py::probe_check_construction_javascript_hc008
# inherits: hd=python/honest-check/honest-check.hd::check_construction -> feature=specs/features/honest-check.feature::check_construction warns for published JavaScript watch-list calls -> test=python/honest-check/conformance/probe_check_construction_javascript_watch_calls.py::probe_check_construction_javascript_watch_calls
# hd: check_construction
def check_construction(ctx):
    """The construction-time rule sub-core (§4.1): HC007, HC003, HC006, HC011, the
    state-machine rules, the vocabulary/binding pairing rules HC004/HC-P013, and
    the link rule HC008, dispatched by the framework constructor each call
    resolves to."""
    composed_findings = []
    for vocab in _calls_named(ctx, "vocabulary"):
        surface = vocabulary_types(ctx, vocab)
        for composition in surface["composed"]:
            name_node = composition["name_node"]
            anchor = name_node or vocab
            name = pick(name_node is None, lambda: "", lambda: f" {literal_string(name_node)!r}")
            references = (("requires", composition["requires_bases"]), ("captures", composition["captures_bases"]))
            for relation, base_names in references:
                for base in sorted(base_names - surface["base_names"]):
                    message = f"Composed type{name} {relation} unknown base type {base!r}"
                    composed_findings.append(diagnostic(ctx, "HC006", "error", message, anchor))
    return (
        _hc007(ctx)
        + _hc003(ctx)
        + composed_findings
        + _hc011(ctx)
        + _hc_state_machines(ctx)
        + _hc004(ctx)
        + _hc_p013(ctx)
        + _hc008(ctx)
    )


# ---- static per-file rules (§4.2) -------------------------------------------

_IF_TYPES = {"if_statement", "conditional_expression", "if_clause"}


def _hc_p001(ctx):
    candidates = filter(lambda n: n.type in _IF_TYPES, ctx["nodes"])
    firing = filter(lambda n: not is_main_guard(ctx, n), candidates)
    return [
        diagnostic(ctx, "HC-P001", "error", "branch not expressed as a dispatch table", n)
        for n in firing
    ]


def _hc_p002(ctx):
    tries = filter(lambda n: n.type == "try_statement", ctx["nodes"])
    caught = filter(lambda t: any(c.type == "except_clause" for c in t.named_children), tries)
    interior = filter(lambda t: in_non_boundary_function(ctx, t), caught)
    return [
        diagnostic(ctx, "HC-P002", "error", "exception caught in a non-boundary function", t)
        for t in interior
    ]


_APPROVED_BASES = {"TypedDict", "Protocol", "ABC", "Exception"}


def _has_approved_base(cls):
    supers = cls.child_by_field_name("superclasses")
    names = pick(
        supers is None,
        lambda: set(),
        lambda: set(c.text.decode("utf-8") for c in filter(lambda c: c.type == "identifier", supers.named_children)),
    )
    return len(names & _APPROVED_BASES) > 0


# inherits: hd=python/honest-check/honest-check.hd::_hc_p003 -> feature=specs/features/honest-check.feature::_hc_p003 reports implicit object inheritance when no actual Python base is declared -> test=python/honest-check/conformance/probe_p003_implicit_bases.py::probe_p003_implicit_bases
# inherits: hd=python/honest-check/honest-check.hd::_hc_p003 -> feature=specs/features/honest-check.feature::_hc_p003 accepts the four approved direct Python bases -> test=python/honest-check/conformance/probe_p003_approved_bases.py::probe_p003_approved_bases
# inherits: hd=python/honest-check/honest-check.hd::_hc_p003 -> feature=specs/features/honest-check.feature::_hc_p003 reports each disallowed direct Python base in source order -> test=python/honest-check/conformance/probe_p003_unauthorized_bases.py::probe_p003_unauthorized_bases
# inherits: hd=python/honest-check/honest-check.hd::_hc_p003 -> feature=specs/features/honest-check.feature::_hc_p003 preserves class-level fallback for disputed and unresolved Python bases -> test=python/honest-check/conformance/probe_p003_disputed_base_fallback.py::probe_p003_disputed_base_fallback
# hd: _hc_p003
def _hc_p003(ctx):
    findings = []
    classes = filter(lambda node: node.type == "class_definition", ctx["nodes"])
    for cls in classes:
        supers = cls.child_by_field_name("superclasses")
        bases = pick(
            supers is None,
            list,
            lambda: list(filter(
                lambda base: base.type not in {"keyword_argument", "dictionary_splat", "comment"},
                supers.named_children,
            )),
        )
        match bool(bases):
            case False:
                findings.append(diagnostic(ctx, "HC-P003", "error", "implicit object inheritance: no declared base", cls))
                continue
        identifiers = filter(lambda base: base.type == "identifier", bases)
        names = map(lambda base: base.text.decode("utf-8"), identifiers)
        disallowed = list(filter(lambda name: name not in _APPROVED_BASES and name != "BaseException", names))
        findings.extend(
            diagnostic(ctx, "HC-P003", "error", f"unauthorized direct base {name!r}", cls)
            for name in disallowed
        )
        match not disallowed and not _has_approved_base(cls):
            case True:
                findings.append(diagnostic(ctx, "HC-P003", "error", "class declaration (inheritance or bare class)", cls))
    return findings


_TYPE_CHECKS = {"isinstance", "type"}


def _hc_p005(ctx):
    calls = filter(lambda n: n.type in _CALL_TYPES, ctx["nodes"])
    firing = filter(
        lambda c: called_name(ctx, c) in _TYPE_CHECKS and in_non_boundary_function(ctx, c),
        calls,
    )
    return [
        diagnostic(ctx, "HC-P005", "warning", "isinstance() or type() in business logic", c)
        for c in firing
    ]


_CACHE_DECORATORS = {"lru_cache", "cache"}


def _hc_p006(ctx):
    decorated = filter(lambda n: n.type == "decorated_definition", ctx["nodes"])
    out = []
    for definition in decorated:
        decorators = filter(lambda c: c.type == "decorator", definition.children)
        cache_decorators = filter(lambda d: decorator_target(d) in _CACHE_DECORATORS, decorators)
        out.extend(
            [
                diagnostic(ctx, "HC-P006", "warning", "cache without a profiling annotation", d)
                for d in cache_decorators
            ]
        )
    return out


def _hc_p007(ctx):
    assignments = filter(lambda n: n.type == "assignment", ctx["nodes"])
    firing = filter(
        lambda a: underscore_self_name(_field(a, "left")) is not None and within_class_init(ctx, a),
        assignments,
    )
    return [
        diagnostic(ctx, "HC-P007", "warning", "instance state in a constructor", a)
        for a in firing
    ]


_LIFECYCLE_HOOKS = {
    "addEventListener", "componentDidMount", "componentWillUnmount", "componentDidUpdate",
    "useEffect", "useLayoutEffect", "ngOnInit", "ngOnDestroy", "connectedCallback",
    "disconnectedCallback",
}


def _top_level_functions(ctx):
    top = ctx["root"].named_children
    direct = list(filter(lambda n: n.type == "function_definition", top))
    decorated = filter(lambda n: n.type == "decorated_definition", top)
    inner = map(
        lambda d: next(filter(lambda c: c.type == "function_definition", d.named_children), None),
        decorated,
    )
    return direct + list(filter(lambda f: f is not None, inner))


def _hc_p014(ctx):
    callable_functions = filter(lambda f: body_has_call(f), _top_level_functions(ctx))
    groups = {}
    for function in callable_functions:
        groups.setdefault(canonical_body(function), []).append(function)
    out = []
    for members in groups.values():
        out.extend(
            pick(
                len(members) > 2,
                lambda: [
                    diagnostic(ctx, "HC-P014", "error", "recognizer reused across slots", min(members, key=lambda f: f.start_byte))
                ],
                lambda: [],
            )
        )
    return out


def _hc_p015(ctx):
    defaults = filter(lambda n: n.type in {"default_parameter", "typed_default_parameter"}, ctx["nodes"])
    firing = filter(lambda d: not is_empty_default(ctx, _field(d, "value")), defaults)
    return [
        diagnostic(ctx, "HC-P015", "error", "implicit default value absorbs the caller's omission", d)
        for d in firing
    ]


def _mutates_nonlocal(ctx, fdef):
    body = own_body(fdef)
    return len(nonlocal_names(body) & mutated_names(ctx, body)) > 0


def _hc_p016(ctx):
    functions = filter(lambda n: n.type == "function_definition", ctx["nodes"])
    firing = filter(lambda f: _mutates_nonlocal(ctx, f), functions)
    return [
        diagnostic(ctx, "HC-P016", "error", "nonlocal closure over mutable state", f)
        for f in firing
    ]


def _is_get_with_default(ctx, call):
    func = _field(call, "function")
    is_get = bool(
        func is not None and func.type == "attribute" and _text(_field(func, "attribute")) == "get"
    )
    return bool(is_get and len(call_arguments(ctx, call)["positionals"]) >= 2)


def _hc_p019(ctx):
    calls = filter(lambda n: n.type in _CALL_TYPES, ctx["nodes"])
    firing = filter(lambda c: _is_get_with_default(ctx, c), calls)
    return [
        diagnostic(ctx, "HC-P019", "error", "lookup with a fallback default serves an unknown key as a known one", c)
        for c in firing
    ]


def _subscript_key(sub):
    value = _field(sub, "value")
    others = list(filter(lambda c: c != value, sub.named_children))
    return pick(len(others) == 0, lambda: None, lambda: others[0])


def _is_open_dispatch(sub, dict_names):
    value = _field(sub, "value")
    key = _subscript_key(sub)
    return bool(
        value is not None
        and value.type == "identifier"
        and value.text.decode("utf-8") in dict_names
        and key is not None
        and key.type == "identifier"
    )


def _hc_p020(ctx):
    dict_names = set(module_dict_literals(ctx).keys())
    subscripts = filter(lambda n: n.type == "subscript", ctx["nodes"])
    firing = filter(lambda s: _is_open_dispatch(s, dict_names), subscripts)
    return [
        diagnostic(ctx, "HC-P020", "error", "dispatch-table subscript with a variable key raises a bare KeyError on a miss", s)
        for s in firing
    ]


def _hc009(ctx):
    out = []
    for vocab in _calls_named(ctx, "vocabulary"):
        base = vocabulary_types(ctx, vocab)["base_types"]
        risky = filter(
            lambda bt: bt["kind"] == "predicate" and predicate_is_risky(bt["recognizer"]),
            base.values(),
        )
        out.extend(
            [
                diagnostic(ctx, "HC009", "warning", "predicate may throw on non-matching input", vocab)
                for _ in risky
            ]
        )
    return out


_SERIALIZABLE_CLASS_BASES = {"TypedDict", "NamedTuple"}


def _class_bases(cls):
    supers = cls.child_by_field_name("superclasses")
    return pick(
        supers is None,
        lambda: set(),
        lambda: set(c.text.decode("utf-8") for c in filter(lambda c: c.type == "identifier", supers.named_children)),
    )


def _nonserializable_class_names(ctx):
    classes = filter(lambda n: n.type == "class_definition", ctx["nodes"])
    out = set()
    for cls in classes:
        name = _field(cls, "name")
        serializable = len(_class_bases(cls) & _SERIALIZABLE_CLASS_BASES) > 0
        out.update(
            pick(name is not None and not serializable, lambda: {name.text.decode("utf-8")}, lambda: set())
        )
    return out


def _returned_expression(return_node):
    return next(filter(lambda c: c.type != "return", return_node.children), None)


def _returns_class_instance(return_node, class_names):
    value = _returned_expression(return_node)
    return bool(
        value is not None
        and value.type == "call"
        and bare_or_final_name(_field(value, "function")) in class_names
    )


def _hc_p010(ctx):
    class_names = _nonserializable_class_names(ctx)
    returns = filter(lambda n: n.type == "return_statement", ctx["nodes"])
    firing = filter(
        lambda r: _returns_class_instance(r, class_names) and in_non_boundary_function(ctx, r),
        returns,
    )
    return [
        diagnostic(ctx, "HC-P010", "error", "pure function returns a non-serializable class instance; use a TypedDict or dict", r)
        for r in firing
    ]


def _hc_hf002(ctx):
    features = features_vocabulary(ctx)
    tables = module_dict_literals(ctx)
    out = []
    for sub in filter(lambda n: n.type == "subscript", ctx["nodes"]):
        value = _field(sub, "value")
        table_name = pick(value is not None and value.type == "identifier", lambda: value.text.decode("utf-8"), lambda: None)
        key = _subscript_key(sub)
        flag = pick(key is not None and key.type in _CALL_TYPES, lambda: feature_state_flag(ctx, key), lambda: None)
        states = read_or(features, flag, None)
        table_keys = read_or(tables, table_name, None)
        missing = pick(states is None or table_keys is None, lambda: set(), lambda: states - table_keys)
        out.extend(
            pick(
                len(missing) > 0,
                lambda: [diagnostic(ctx, "HC-HF002", "warning", "handler table missing an entry for a declared flag state", sub)],
                lambda: [],
            )
        )
    return out


# The closed set of HTTP response types §HC-P017 reads off a return annotation. A
# function annotated to return one of these produces HTTP output, and must be a @link
# with an emits vocabulary (or compose with a serializer @link) so its output is
# classified and testable.
_HTTP_RESPONSE_TYPES = {
    "Response", "HTMLResponse", "JSONResponse", "TemplateResponse",
    "PlainTextResponse", "RedirectResponse", "StreamingResponse", "FileResponse",
}


def _annotation_identifiers(annotation):
    nested = set(n.text.decode("utf-8") for n in filter(lambda n: n.type == "identifier", walk(annotation)))
    bare = pick(annotation.type == "identifier", lambda: {annotation.text.decode("utf-8")}, lambda: set())
    return nested | bare


def _returns_http_response(fdef):
    annotation = _field(fdef, "return_type")
    names = pick(annotation is None, lambda: set(), lambda: _annotation_identifiers(annotation))
    return len(names & _HTTP_RESPONSE_TYPES) > 0


def _hc_p017(ctx):
    functions = filter(lambda n: n.type == "function_definition", ctx["nodes"])
    firing = filter(lambda f: _returns_http_response(f) and not link_declares_emits(ctx, f), functions)
    return [
        diagnostic(ctx, "HC-P017", "error", "function produces an HTTP response without being a declared @link with an emits vocabulary", f)
        for f in firing
    ]


# inherits: hd=python/honest-check/honest-check.hd::check_per_file -> feature=specs/features/honest-check.feature::check_per_file reports an emitted type neither produced nor accepted without a companion declaration -> test=python/honest-check/conformance/probe_check_per_file_hc010_phantom.py::probe_check_per_file_hc010_phantom
# inherits: hd=python/honest-check/honest-check.hd::check_per_file -> feature=specs/features/honest-check.feature::check_per_file allows an emitted type produced by a manifest assignment -> test=python/honest-check/conformance/probe_check_per_file_hc010_produced.py::probe_check_per_file_hc010_produced
# inherits: hd=python/honest-check/honest-check.hd::check_per_file -> feature=specs/features/honest-check.feature::check_per_file allows an emitted type accepted by the link -> test=python/honest-check/conformance/probe_check_per_file_hc010_accepted.py::probe_check_per_file_hc010_accepted
# inherits: hd=python/honest-check/honest-check.hd::check_per_file -> feature=specs/features/honest-check.feature::check_per_file does not warn on a link with no declared emitted types -> test=python/honest-check/conformance/probe_check_per_file_hc010_undeclared.py::probe_check_per_file_hc010_undeclared
# inherits: hd=python/honest-check/honest-check.hd::check_per_file -> feature=specs/features/honest-check.feature::check_per_file skips automatic binding -> test=python/honest-check/conformance/probe_check_per_file_hc005_automatic.py::probe_check_per_file_hc005_automatic
# inherits: hd=python/honest-check/honest-check.hd::check_per_file -> feature=specs/features/honest-check.feature::check_per_file allows an explicit binding for a declared base type -> test=python/honest-check/conformance/probe_check_per_file_hc005_base.py::probe_check_per_file_hc005_base
# inherits: hd=python/honest-check/honest-check.hd::check_per_file -> feature=specs/features/honest-check.feature::check_per_file allows an explicit binding for a declared composed type -> test=python/honest-check/conformance/probe_check_per_file_hc005_composed.py::probe_check_per_file_hc005_composed
# inherits: hd=python/honest-check/honest-check.hd::check_per_file -> feature=specs/features/honest-check.feature::check_per_file warns for an unknown explicit binding key -> test=python/honest-check/conformance/probe_check_per_file_hc005_unknown.py::probe_check_per_file_hc005_unknown
# inherits: hd=python/honest-check/honest-check.hd::check_per_file -> feature=specs/features/honest-check.feature::check_per_file reports an unknown literal flag against an explicitly empty FEATURES vocabulary -> test=python/honest-check/conformance/probe_check_per_file_empty_features.py::probe_check_per_file_empty_features
# inherits: hd=python/honest-check/honest-check.hd::check_per_file -> feature=specs/features/honest-check.feature::check_per_file skips local feature rules when FEATURES is absent or unreadable -> test=python/honest-check/conformance/probe_check_per_file_unreadable_features.py::probe_check_per_file_unreadable_features
# inherits: hd=python/honest-check/honest-check.hd::check_per_file -> feature=specs/features/honest-check.feature::check_per_file reports qualified JavaScript lifecycle calls -> test=python/honest-check/conformance/probe_check_per_file_javascript_lifecycle.py::probe_check_per_file_javascript_lifecycle
# inherits: hd=python/honest-check/honest-check.hd::check_per_file -> feature=specs/features/honest-check.feature::check_per_file reports only real-valued Python numeric defaults -> test=python/honest-check/conformance/probe_check_per_file_numeric_defaults.py::probe_check_per_file_numeric_defaults
# inherits: hd=python/honest-check/honest-check.hd::check_per_file -> feature=specs/features/honest-check.feature::check_per_file reports a disallowed Python base alongside an approved base -> test=python/honest-check/conformance/probe_p003_through_check_per_file.py::probe_p003_through_check_per_file
# inherits: hd=python/honest-check/honest-check.hd::check_per_file -> feature=specs/features/honest-check.feature::check_per_file reports HC-P004 for named JavaScript Ruby and Go functions -> test=python/honest-check/conformance/probe_p004_check_per_file_cross_language_p004.py::probe_p004_check_per_file_cross_language_p004
# hd: check_per_file
def check_per_file(ctx):
    """The static per-file rule sub-core (§4.2): the HC-P purity rules, the predicate
    rules HC005, HC009, and HC010, the non-serializable-return rule
    HC-P010, the undeclared-serializer rule HC-P017 and the feature-flag rules
    HC-HF001/HC-HF002, folded over the declaration
    graph."""
    binding_findings = []
    for vocabs, binding in vocabulary_binding_pairs(ctx):
        known = set()
        for vocab in vocabs:
            surface = vocabulary_types(ctx, vocab)
            known.update(surface["base_names"], surface["composed_type_names"])
        binding_findings.extend(
            diagnostic(ctx, "HC005", "warning", f"binding references undefined vocabulary type {key!r}", binding)
            for key in sorted(binding_keys(ctx, binding) - known)
        )
    calls = list(filter(lambda node: node.type in _CALL_TYPES, ctx["nodes"]))
    named_calls = ((call, called_name(ctx, call)) for call in calls)
    lifecycle_findings = [
        diagnostic(
            ctx, "HC-P011", "error",
            f"Lifecycle hook {name!r}. Use HTMX attributes or server-rendered HTML.",
            call,
        )
        for call, name in filter(lambda entry: entry[1] in _LIFECYCLE_HOOKS, named_calls)
    ]
    tables = module_dict_literals(ctx)
    feature_findings = []
    for call in pick("FEATURES" in tables, lambda: calls, list):
        flag = feature_state_flag(ctx, call)
        fire = flag is not None and flag not in tables["FEATURES"]
        feature_findings.extend(
            pick(
                fire,
                lambda: [diagnostic(ctx, "HC-HF001", "error", f"feature_state references a flag not declared in FEATURES: {flag!r}", call)],
                list,
            )
        )
    return (
        binding_findings
        + _hc010(ctx)
        + _hc_p001(ctx)
        + _hc_p002(ctx)
        + _hc_p003(ctx)
        + _hc_p004(ctx)
        + _hc_p005(ctx)
        + _hc_p006(ctx)
        + _hc_p007(ctx)
        + _hc_p010(ctx)
        + lifecycle_findings
        + _hc_p014(ctx)
        + _hc_p015(ctx)
        + _hc_p016(ctx)
        + _hc_p017(ctx)
        + _hc_p019(ctx)
        + _hc_p020(ctx)
        + _hc009(ctx)
        + feature_findings
        + _hc_hf002(ctx)
    )


# ---- the rule-running core (§3.4) -------------------------------------------


def _roles_from(declaration):
    return {fn["name"]: fn["role"] for fn in declaration["functions"]}


def _with_roles(context, declaration):
    roles = pick(declaration is None, lambda: context["roles"], lambda: _roles_from(declaration))
    return {**context, "roles": roles}


def _run_rules(context, declaration):
    ctx = _with_roles(context, declaration)
    combined = check_construction(ctx) + check_per_file(ctx)
    return apply_suppression(ctx, combined)


def check_source(context, declaration):
    """The pure rule-running core (§3.4): the HC-SYN parse gate first, then the two
    rule sub-cores and the suppression pass. A violation returns as a Diagnostic,
    never an exception."""
    return pick(
        context["root"].has_error,
        lambda: [file_diagnostic(context["path"], "HC-SYN", "error", "source does not parse")],
        lambda: _run_rules(context, declaration),
    )
