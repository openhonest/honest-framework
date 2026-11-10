"""honest-check per-file rule sub-core, split from core.py for L1.17 (section 4.2)."""

import itertools
from honest_parse import language_of, line_col
from honest_check.watchlists import IO_WATCH_LIST, NONDETERMINISTIC_WATCH_LIST
from honest_check.constants import _APPROVED_BASES, _CACHE_DECORATORS, _HTTP_RESPONSE_MARKERS, _IO_CALLS, _IO_MODULE_PREFIXES, _LIFECYCLE_HOOKS, _TYPE_CHECK_CALLS
from honest_check.nodes import base_types_of, call_arguments, called_name, canonical_name, decorator_expression, decorator_target, decorators_of, diagnostic, enclosing_function, in_non_boundary_function, is_boundary_decorator, literal_string, module_mutable_globals, nonlocal_names, own_body, param_names, underscore_self_name
from honest_check.analysis import construction_maps, dispatch_variable, dotted_target, feature_state_flag, features_vocabulary, is_empty_default, is_link_decorated, is_orchestrator, link_declares_emits, link_is_impure, local_function_links, longest_shared_run, module_dict_literals, mutated_names, persist_write_targets, within_class_init
from honest_check.bindings import binding_keys, vocabulary_binding_pairs, vocabulary_types


def check_per_file(ctx):
    """Per-file rules (section 4.2): the HC-P purity rules, the HC chain/link rules, and the
    HC-HF feature rules, folded over the declaration graph. The per-rule logic nests here as
    data; ctx carries the parse."""
    nodes = ctx["nodes"]
    path = ctx["path"]
    rule_config = ctx["rule_config"]
    def check_classes():
        """HC-P003: a bare class, or a class inheriting a non-approved base (section 4.1)."""
        findings = []
        for node in nodes:
            if node.type != "class_definition":
                continue
            name_node = node.child_by_field_name("name")
            name = name_node.text.decode("utf-8")
            superclasses = node.child_by_field_name("superclasses")
            # A class's base list carries positional bases and keyword arguments alike
            # (TypedDict's `total=False`, a metaclass= or an __init_subclass__ keyword). A
            # keyword argument configures the class, it is not a base, so it is not an
            # inheritance the rule judges — only the positional bases are.
            bases = (
                [c for c in superclasses.named_children if c.type != "keyword_argument"]
                if superclasses is not None
                else []
            )
            if not bases:
                findings.append(
                    diagnostic(ctx,
                        "HC-P003",
                        "error",
                        f"Class {name!r} has no declared base. Use a TypedDict for data "
                        "shapes or a pure function.",
                        node,
                    )
                )
                continue
            for base in bases:
                if base.text.decode("utf-8") not in _APPROVED_BASES:
                    findings.append(
                        diagnostic(ctx,
                            "HC-P003",
                            "error",
                            f"Class {name!r} inherits from {base.text.decode('utf-8')!r}. "
                            "Use composition over inheritance.",
                            node,
                        )
                    )
        return findings

    def check_p001():
        """HC-P001: an if/elif chain of three or more branches that dispatch on one variable's
        value — three or more equality tests on the same variable across if/elif. Reported at
        the `if` statement's line (§4.2)."""
        findings = []
        for node in nodes:
            if node.type != "if_statement":
                continue
            conditions = [node.child_by_field_name("condition")]
            for child in node.named_children:
                if child.type == "elif_clause":
                    conditions.append(child.child_by_field_name("condition"))
            variables = [
                variable
                for variable in (dispatch_variable(ctx, c) for c in conditions)
                if variable is not None
            ]
            if any(variables.count(variable) >= 3 for variable in set(variables)):
                findings.append(
                    diagnostic(ctx,
                        "HC-P001",
                        "error",
                        "if/elif/else chain dispatches on value — use dict lookup. "
                        "See honest-code-principles.md §3.",
                        node,
                    )
                )
        return findings

    def check_p007():
        """HC-P007: inside a class __init__, an assignment to a `self._name` attribute whose
        name starts with an underscore — hidden instance state. Reported at the assignment's
        line (§4.2)."""
        findings = []
        for node in nodes:
            if node.type != "assignment":
                continue
            name = underscore_self_name(node.child_by_field_name("left"))
            if name is None or not within_class_init(ctx, node):
                continue
            findings.append(
                diagnostic(ctx,
                    "HC-P007",
                    "warning",
                    f"Instance state {name!r}. Pass as parameter or use context manager.",
                    node,
                )
            )
        return findings

    def check_p011():
        """HC-P011: a call whose name is a framework lifecycle hook (§4.2). Reported at the
        call's line."""
        findings = []
        for node in nodes:
            if node.type != "call":
                continue
            name = called_name(ctx, node)
            if name in _LIFECYCLE_HOOKS:
                findings.append(
                    diagnostic(ctx,
                        "HC-P011",
                        "error",
                        f"Lifecycle hook {name!r}. Use HTMX attributes or server-rendered "
                        "HTML.",
                        node,
                    )
                )
        return findings

    def check_p016():
        """HC-P016: an inner (nested) function that declares `nonlocal X` and mutates X by
        assignment or augmented assignment. Reported at the inner function's `def` line
        (§4.2)."""
        findings = []
        for node in nodes:
            if node.type != "function_definition" or enclosing_function(node) is None:
                continue
            statements = own_body(node)
            hit = sorted(nonlocal_names(statements) & mutated_names(ctx, statements))
            if not hit:
                continue
            name_node = node.child_by_field_name("name")
            inner = name_node.text.decode("utf-8")
            findings.append(
                diagnostic(ctx,
                    "HC-P016",
                    "error",
                    f"Inner function {inner!r} captures {hit[0]!r} via nonlocal and mutates "
                    "it. Closures may not carry mutable state — use pure parameters or move "
                    "state into persist.",
                    node,
                )
            )
        return findings

    def check_p002():
        """HC-P002: a `try` with an `except` clause inside a non-boundary function — business
        logic that swallows a fault instead of letting it raise to the boundary (§4.2, §5.2).
        A `try`/`finally` with no `except` does not fire. Reported at the `try`'s line."""
        findings = []
        for node in nodes:
            if node.type != "try_statement":
                continue
            if not any(child.type == "except_clause" for child in node.named_children):
                continue
            if not in_non_boundary_function(ctx, node):
                continue
            function = enclosing_function(node)
            name_node = function.child_by_field_name("name")
            name = name_node.text.decode("utf-8")
            findings.append(
                diagnostic(ctx,
                    "HC-P002",
                    "error",
                    f"Function {name!r} catches an exception in business logic. Let the "
                    "function raise; catch at the boundary (@boundary / route handler), or "
                    "return a fault as data.",
                    node,
                )
            )
        return findings

    def check_p004():
        """HC-P004: a call to Python I/O in a non-boundary function (§5.4) — a whole-name hit
        on _IO_CALLS or a dotted-prefix hit on _IO_MODULE_PREFIXES. Reported at the call's
        line."""
        findings = []
        for node in nodes:
            if node.type != "call":
                continue
            target = dotted_target(ctx, node)
            if target is None:
                continue
            is_io = target in _IO_CALLS or any(
                target.startswith(prefix) for prefix in _IO_MODULE_PREFIXES
            )
            if not is_io or not in_non_boundary_function(ctx, node):
                continue
            findings.append(
                diagnostic(ctx,
                    "HC-P004",
                    "error",
                    f"I/O call {target!r} in a non-boundary function reaches outside the "
                    "process off the boundary. Do the I/O at a boundary (@boundary / route "
                    "handler) and pass the result into the pure interior.",
                    node,
                )
            )
        return findings

    def check_st001():
        """HC-ST001: a call to a honest-persist database writer in a non-boundary function
        (§3.1, honest-state-architecture.md) — a write to persisted state off the boundary.
        The writers are the functions honest-persist declares with `side_effect writes
        "database"` (`transaction`, `apply`); persist_write_targets resolves them through this
        file's own `honest_persist` imports, so a bare name no such import binds does not fire,
        and `insert`/`update`/`delete` — pure Query builders — never fire. Boundary-ness is the
        same test HC-P004 uses: a `@boundary` function, or one the module's `.hd` marks a door,
        is the legitimate boundary write and is dropped. honest-persist's own package is not
        policed — its interior names these functions as local defs, so nothing resolves.
        Reported at the call's line."""
        findings = []
        targets = persist_write_targets(ctx)
        if not targets:
            return findings
        for node in nodes:
            if node.type != "call":
                continue
            target = dotted_target(ctx, node)
            if target is None or target not in targets:
                continue
            if not in_non_boundary_function(ctx, node):
                continue
            findings.append(
                diagnostic(ctx,
                    "HC-ST001",
                    "error",
                    f"Persisted-state write {target!r} in a non-boundary function writes the "
                    "database off the boundary. Do the write at a boundary (@boundary / route "
                    "handler), not in the pure interior.",
                    node,
                )
            )
        return findings

    def check_p005():
        """HC-P005: a call to `isinstance` or `type` in a non-boundary function — a runtime
        type check that should be a vocabulary declared at the boundary (§5.5). Reported at
        the call's line."""
        findings = []
        for node in nodes:
            if node.type != "call":
                continue
            function = node.child_by_field_name("function")
            if function is None or function.type != "identifier":
                continue
            if function.text.decode("utf-8") not in _TYPE_CHECK_CALLS:
                continue
            if not in_non_boundary_function(ctx, node):
                continue
            findings.append(
                diagnostic(ctx,
                    "HC-P005",
                    "warning",
                    "Runtime type check in business logic. Declare the constraint as a "
                    "vocabulary at the boundary instead.",
                    node,
                )
            )
        return findings

    def check_p006():
        """HC-P006: a cache decorator on a function that carries no profiling note — no
        evidence the cache was measured (§5.6). A profiling note is a `@profiled` decorator on
        the same function, or a `# honest: profiled` comment on the contiguous line(s)
        immediately above the construct. Reported at the cache decorator's line."""
        comment_lines = {}
        for node in nodes:
            if node.type != "comment":
                continue
            line, _col = line_col(node)
            raw = node.text.decode("utf-8") if node.text else ""
            comment_lines[line] = raw.lstrip("#").strip()

        def profiled_above(top_line):
            line = top_line - 1
            while line in comment_lines:
                if comment_lines[line] == "honest: profiled":
                    return True
                line -= 1
            return False

        findings = []
        for node in nodes:
            if node.type != "decorated_definition":
                continue
            decorators = [c for c in node.children if c.type == "decorator"]
            cache_decorators = [
                d for d in decorators if decorator_target(d) in _CACHE_DECORATORS
            ]
            if not cache_decorators:
                continue
            has_profiled_decorator = any(
                decorator_target(d) == "profiled" for d in decorators
            )
            top_line, _col = line_col(node)
            if has_profiled_decorator or profiled_above(top_line):
                continue
            findings.append(
                diagnostic(ctx,
                    "HC-P006",
                    "warning",
                    "Cache decorator without a profiling note. Add a @profiled decorator or "
                    "a '# honest: profiled' comment proving the cache was measured.",
                    cache_decorators[0],
                )
            )
        return findings

    def check_p015():
        """HC-P015: a parameter whose default value is a real, non-empty value (§HC-P015). A
        real-valued default absorbs the caller's omission and leaves the omitted-argument path
        untested. Reported at the parameter's line; an empty default (the honest nothing) does
        not fire."""
        findings = []
        for node in nodes:
            if node.type not in ("default_parameter", "typed_default_parameter"):
                continue
            value = node.child_by_field_name("value")
            if value is None or is_empty_default(ctx, value):
                continue
            name_node = node.child_by_field_name("name")
            name = name_node.text.decode("utf-8")
            findings.append(
                diagnostic(ctx,
                    "HC-P015",
                    "error",
                    f"Parameter {name!r} defaults to a real value. A default hides whether "
                    "the caller chose the value or omitted it, and leaves the omitted-argument "
                    "path untested. Make the parameter required, or default it to empty if "
                    "absence is the honest nothing.",
                    node,
                )
            )
        return findings

    def check_hc008():
        """HC008: a non-boundary `@link` whose body calls a function on the impurity watch
        list for the file's language, or reads a module-level mutable global (§HC008). A
        `@link(boundary=True)` or `@boundary` link is exempt. Reported once, at the link's
        `def` line. The watch lists are keyed by the language honest-parse detected for this
        path; a language with no published list has an empty watch, so the call clause is
        inert for it."""
        language = language_of(path).get("ok")
        io = IO_WATCH_LIST[language] if language in IO_WATCH_LIST else frozenset()
        nondeterministic = (
            NONDETERMINISTIC_WATCH_LIST[language]
            if language in NONDETERMINISTIC_WATCH_LIST
            else frozenset()
        )
        watch = io | nondeterministic
        mutable_globals = module_mutable_globals(ctx)
        findings = []
        for node in nodes:
            if node.type != "function_definition":
                continue
            if not is_link_decorated(ctx, node):
                continue
            if any(is_boundary_decorator(ctx, d) for d in decorators_of(ctx, node)):
                continue
            if not link_is_impure(ctx, node, watch, mutable_globals):
                continue
            name_node = node.child_by_field_name("name")
            name = name_node.text.decode("utf-8")
            findings.append(
                diagnostic(ctx,
                    "HC008",
                    "warning",
                    f"Link {name!r} may be impure: it calls a watched function or reads "
                    "module-level mutable state. Add boundary=True if the I/O is intentional.",
                    node,
                )
            )
        return findings

    def check_hc001():
        """HC001: a `chain()` link that resolves to a locally-defined function carrying no
        `@link` declaration, so its vocabulary is undeclared and the chain cannot be
        contract-tested (§4.2). Reported at the `chain()` call's line. A positional that
        resolves to no local function — an import or an expression — is skipped: honest-check
        cannot see its declaration, and a miss is preferred to a false positive here."""
        links = local_function_links(ctx)
        findings = []
        for node in nodes:
            if node.type != "call" or canonical_name(ctx, node) != "chain":
                continue
            positionals, _keywords = call_arguments(ctx, node)
            for argument in positionals:
                if argument.type != "identifier":
                    continue
                name = argument.text.decode("utf-8")
                if name not in links or links[name]:
                    continue
                findings.append(
                    diagnostic(ctx,
                        "HC001",
                        "error",
                        f"Chain link {name!r} has no vocabulary declared. Wrap it with "
                        "@link(accepts=..., emits=...) or the link() constructor.",
                        node,
                    )
                )
        return findings

    def check_hc_or001():
        """HC-OR001: a declared orchestrator whose own body calls another function the file
        declares an orchestrator — orchestrator composition, the invisible nesting the
        architecture forbids (§4.2). Reported at the calling site's line. The body walk is the
        orchestrator's own, not a nested scope's."""
        orchestrators = []
        names = set()
        for node in nodes:
            if node.type != "function_definition" or not is_orchestrator(ctx, node):
                continue
            name_node = node.child_by_field_name("name")
            name = name_node.text.decode("utf-8")
            orchestrators.append((node, name))
            names.add(name)
        findings = []
        for fdef, name in orchestrators:
            for statement in own_body(fdef):
                if statement.type != "call":
                    continue
                callee = called_name(ctx, statement)
                if callee not in names:
                    continue
                findings.append(
                    diagnostic(ctx,
                        "HC-OR001",
                        "error",
                        f"Orchestrator {name!r} calls orchestrator {callee!r}. "
                        "Orchestrators are the root of an operation and do not compose. "
                        "Extract the shared logic as a pure helper (if no I/O) or as a chain "
                        "(if I/O is involved).",
                        statement,
                    )
                )
        return findings

    def check_hc_or003():
        """HC-OR003: two orchestrators that share a run of `min_run` or more consecutive
        equivalent calls — latent duplication evolving toward a shared pattern the architecture
        would extract (§HC-OR003). A soft warning. `min_run` has no built-in default: it reaches
        the rule only through rule_config, and when it is absent the rule does not run and emits
        nothing, so a chosen threshold is never confused with one nobody set. Each orchestrator's
        body is normalized to the sequence of call names it makes, in source order; the shared
        run is the longest contiguous common run of those names. Reported once per pair, at the
        later orchestrator's `def` line."""
        min_run = rule_config.get("HC-OR003", {}).get("min_run")
        if min_run is None:
            return []
        orchestrators = []
        for node in nodes:
            if node.type != "function_definition" or not is_orchestrator(ctx, node):
                continue
            name_node = node.child_by_field_name("name")
            name = name_node.text.decode("utf-8")
            calls = [
                called_name(ctx, statement)
                for statement in own_body(node)
                if statement.type == "call"
            ]
            orchestrators.append((node, name, calls))
        findings = []
        for (_node_a, name_a, calls_a), (node_b, name_b, calls_b) in itertools.combinations(
            orchestrators, 2
        ):
            run = longest_shared_run(ctx, calls_a, calls_b)
            if run < min_run:
                continue
            findings.append(
                diagnostic(ctx,
                    "HC-OR003",
                    "warning",
                    f"Orchestrators {name_a!r} and {name_b!r} share {run} consecutive "
                    "operations. Consider extracting the shared sequence as a pure helper "
                    "(if side-effect-free) or as a chain (if I/O is involved). Orchestrators "
                    "are not composable (HC-OR001); reusable orchestration logic belongs in "
                    "helpers or chains.",
                    node_b,
                )
            )
        return findings

    def check_p017():
        """HC-P017: a function whose own body calls an HTTP-response marker produces HTTP output
        (§HC-P017). It fires unless the function is a `@link` whose `emits` vocabulary is
        declared, because otherwise its serialized output is classified by no vocabulary and
        escapes chain-contract testing. Reported at the function's `def` line."""
        findings = []
        for node in nodes:
            if node.type != "function_definition":
                continue
            produces_http = any(
                called_name(ctx, child) in _HTTP_RESPONSE_MARKERS
                for child in own_body(node)
                if child.type == "call"
            )
            if not produces_http:
                continue
            if is_link_decorated(ctx, node) and link_declares_emits(ctx, node):
                continue
            name_node = node.child_by_field_name("name")
            name = name_node.text.decode("utf-8")
            findings.append(
                diagnostic(ctx,
                    "HC-P017",
                    "error",
                    f"Function {name!r} produces HTTP output without being a declared @link "
                    "with an emits vocabulary. Declare emits covering status, content-type, "
                    "body shape, headers, and cookies, or delegate to a declared serializer "
                    "link.",
                    node,
                )
            )
        return findings

    def check_hc004():
        """HC004: a vocabulary base type the paired binding never binds and no composed type
        uses, in its requires or as its captures, is dead (§HC004). Reported at the
        vocabulary() call that declares the dead type, once per dead type. A link crosses the
        binding against the union of its accepts and emits vocabularies, so a composed type in
        either rescues a base type in either. A classify with no bind, or a link with no binds,
        pairs the identity auto_binding and does not fire."""
        findings = []
        for vocab_calls, binding_call in vocabulary_binding_pairs(ctx):
            bound = binding_keys(ctx, binding_call)
            composed_requires = set()
            composed_captures = set()
            per_vocab_bases = []
            for vocab_call in vocab_calls:
                base_names, _composed_names, requires, captures = vocabulary_types(ctx, vocab_call)
                per_vocab_bases.append((vocab_call, base_names))
                composed_requires |= requires
                composed_captures |= captures
            for vocab_call, base_names in per_vocab_bases:
                for type_name in sorted(base_names):
                    if type_name in bound:
                        continue
                    if type_name in composed_requires or type_name in composed_captures:
                        continue
                    findings.append(
                        diagnostic(ctx,
                            "HC004",
                            "warning",
                            f"Type {type_name!r} is declared in the vocabulary but no binding "
                            "slot or composed type uses it. Bind it to a slot, use it in a "
                            "composed type, or remove it from the vocabulary.",
                            vocab_call,
                        )
                    )
        return findings

    def check_hc005():
        """HC005: a binding key that names neither a base type nor a composed type of the
        paired vocabulary binds a type no token can carry (§HC005). Reported at the binding()
        call's line, once per unmatched key. A link crosses the binding against the union of its
        accepts and emits vocabularies, so an emit-type binding entry is bound, not unmatched. A
        classify with no bind, or a link with no binds, pairs the identity auto_binding and does
        not fire."""
        findings = []
        for vocab_calls, binding_call in vocabulary_binding_pairs(ctx):
            known = set()
            for vocab_call in vocab_calls:
                base_names, composed_names, _requires, _captures = vocabulary_types(ctx, vocab_call)
                known |= base_names | composed_names
            for type_name in sorted(binding_keys(ctx, binding_call)):
                if type_name in known:
                    continue
                findings.append(
                    diagnostic(ctx,
                        "HC005",
                        "warning",
                        f"Binding references type {type_name!r} not found in the paired "
                        "vocabulary, so no classified token can reach its slot. Add the type "
                        "to the vocabulary, or remove the binding entry.",
                        binding_call,
                    )
                )
        return findings

    def check_p010():
        """HC-P010: a pure (non-boundary) function that returns an instance of a class this
        file defines and that is not a TypedDict (§HC-P010). A TypedDict instance is a dict,
        so it crosses a boundary as serializable data and is exempt; any other locally-defined
        class is an opaque, behaviour-bearing object. Reported at the return statement. The
        check reads only classes declared in this file: an imported name carries no class-ness
        the tree can see, so a return of an imported constructor is not judged here."""
        opaque_classes = set()
        for node in nodes:
            if node.type != "class_definition":
                continue
            superclasses = node.child_by_field_name("superclasses")
            bases = (
                [c.text.decode("utf-8") for c in superclasses.named_children if c.type != "keyword_argument"]
                if superclasses is not None
                else []
            )
            if "TypedDict" in bases:
                continue
            opaque_classes.add(node.child_by_field_name("name").text.decode("utf-8"))
        findings = []
        for node in nodes:
            if node.type != "return_statement":
                continue
            value = node.named_children[0] if node.named_children else None
            if value is None or value.type != "call":
                continue
            function = value.child_by_field_name("function")
            if function is None or function.type != "identifier":
                continue
            name = function.text.decode("utf-8")
            if name not in opaque_classes:
                continue
            if not in_non_boundary_function(ctx, node):
                continue
            findings.append(
                diagnostic(ctx,
                    "HC-P010",
                    "error",
                    f"Pure function returns an instance of {name!r}, an opaque object rather "
                    "than serializable data. Return a dict or a TypedDict so the value crosses "
                    "the boundary as data.",
                    node,
                )
            )
        return findings

    def check_p013():
        """HC-P013: a routing-key slot — db_id, tenant_id, or credential — bound to a type
        whose recognizer is a predicate rather than a bounded Set (§HC-P013, honest-persist
        §8.4). A predicate accepts any string the pool would then try to reach, so a caller
        can name a database the application never declared; a bounded Set makes the reachable
        set a closed, declared list. Reported at the binding() call, once per offending entry.
        A set recognizer is honest and does not fire; a ref recognizer resolves elsewhere and
        is out of scope for this structural check, so only the predicate kind is flagged."""
        routing_keys = {"db_id", "tenant_id", "credential"}
        findings = []
        for vocab_calls, binding_call in vocabulary_binding_pairs(ctx):
            kinds = {}
            for vocab_call in vocab_calls:
                positionals, _keywords = call_arguments(ctx, vocab_call)
                if positionals and positionals[0].type == "dictionary":
                    for name, (kind, _payload) in base_types_of(ctx, positionals[0]).items():
                        kinds[name] = kind
            positionals, _keywords = call_arguments(ctx, binding_call)
            if not positionals or positionals[0].type != "dictionary":
                continue
            for pair in positionals[0].named_children:
                if pair.type != "pair":
                    continue
                type_name = literal_string(pair.child_by_field_name("key"))
                slot = literal_string(pair.child_by_field_name("value"))
                if slot not in routing_keys or kinds.get(type_name) != "predicate":
                    continue
                findings.append(
                    diagnostic(ctx,
                        "HC-P013",
                        "error",
                        f"Routing key {slot!r} is bound to predicate recognizer "
                        f"{type_name!r}. A predicate accepts any string the pool would try "
                        "to reach; bind a bounded Set recognizer so the reachable set is a "
                        "closed, declared list.",
                        binding_call,
                    )
                )
        return findings

    def check_hc010():
        """HC010: a declared @link whose emits vocabulary names a type its body never produces
        (§"Declared emission never produced"). For a `@link(accepts=A, emits=E, binds=B)`, a
        type E names, that the body never writes to the manifest and A does not already carry,
        is a phantom emission: the link promises to produce it and does not. The body produces a
        type by writing the manifest slot that type binds to — a subscript assignment
        `<p>["slot"] = ...` on the link's first parameter `<p>`, read back through B's
        slot-to-type inverse. Reported once at the link's def line, naming the phantom types. A
        link whose emits or binds argument is not a plain name, or resolves to no local
        construction, is skipped — honest-check cannot cross what it was not handed."""
        vocab_calls, binding_calls = construction_maps(ctx)
        findings = []
        for node in nodes:
            if node.type != "function_definition":
                continue
            link_call = None
            for decorator in decorators_of(ctx, node):
                if decorator_target(decorator) != "link":
                    continue
                expr = decorator_expression(decorator)
                if expr.type == "call":
                    link_call = expr
                break
            if link_call is None:
                continue
            _positionals, keywords = call_arguments(ctx, link_call)
            emits_arg = keywords.get("emits")
            binds_arg = keywords.get("binds")
            accepts_arg = keywords.get("accepts")
            if (
                emits_arg is None
                or emits_arg.type != "identifier"
                or binds_arg is None
                or binds_arg.type != "identifier"
            ):
                continue
            emits_call = vocab_calls.get(emits_arg.text.decode("utf-8"))
            binding_call = binding_calls.get(binds_arg.text.decode("utf-8"))
            if emits_call is None or binding_call is None:
                continue
            emitted_types, _emits_composed, _requires, _captures = vocabulary_types(ctx, emits_call)
            accepts_types = set()
            if accepts_arg is not None and accepts_arg.type == "identifier":
                accepts_call = vocab_calls.get(accepts_arg.text.decode("utf-8"))
                if accepts_call is not None:
                    accepts_types, _a_composed, _ar, _ac = vocabulary_types(ctx, accepts_call)
            binding_reverse = {}
            b_positionals, _b_keywords = call_arguments(ctx, binding_call)
            if b_positionals and b_positionals[0].type == "dictionary":
                for pair in b_positionals[0].named_children:
                    if pair.type != "pair":
                        continue
                    slot_value = pair.child_by_field_name("value")
                    if slot_value is not None and slot_value.type == "string":
                        binding_reverse[literal_string(slot_value)] = literal_string(
                            pair.child_by_field_name("key")
                        )
            first_param = None
            params = node.child_by_field_name("parameters")
            for child in params.named_children:
                if child.type == "comment":
                    continue
                names = param_names(child)
                if names:
                    first_param = next(iter(names))
                break
            produced_keys = set()
            if first_param is not None:
                for statement in own_body(node):
                    if statement.type != "assignment":
                        continue
                    target = statement.child_by_field_name("left")
                    if target is None or target.type != "subscript":
                        continue
                    obj = target.child_by_field_name("value")
                    index = target.child_by_field_name("subscript")
                    if obj is None or obj.type != "identifier":
                        continue
                    if obj.text.decode("utf-8") != first_param:
                        continue
                    if index is None or index.type != "string":
                        continue
                    produced_keys.add(literal_string(index))
            produced_types = {
                binding_reverse[key] for key in produced_keys if key in binding_reverse
            }
            phantom = emitted_types - produced_types - accepts_types
            if not phantom:
                continue
            name_node = node.child_by_field_name("name")
            name = name_node.text.decode("utf-8")
            findings.append(
                diagnostic(ctx,
                    "HC010",
                    "warning",
                    f"Link {name!r} declares it emits {sorted(phantom)} but its body never "
                    "produces them: it writes no manifest slot bound to the type and does not "
                    "accept the type. Write the slot, drop the type from emits, or accept it.",
                    node,
                )
            )
        return findings

    def check_hc002():
        """HC002: a chain seam whose adjacent links disagree on type — a link that accepts a
        type the previous link does not emit, so the chain cannot be contract-tested at that
        seam (§"Chain type mismatch"). For each chain() call, its positional links resolve in
        order to their local @link definitions; for each adjacent pair (link i-1, link i) from
        i=1, the types link i accepts that link i-1 does not emit are missing, and a non-empty
        missing set fires once at the chain() call's line, naming link i and the missing types.
        A positional that resolves to no local @link is skipped, so neither pair touching it
        fires — HC001 already reports an undeclared chain link. A keyword may name a single
        vocabulary or a `|` union of vocabularies; a union resolves to the union of the named
        vocabularies' base-type names (the same emits resolution HC010 reads). The first link's
        accepts is left unchecked here: its input is the derived boundary vocabulary (spec
        §497, the route-map/template derivation), which needs cross-artifact inputs honest-check
        does not ingest yet."""
        vocab_calls, _binding_calls = construction_maps(ctx)

        def vocab_arg_type_names(arg):
            """The base-type names a link's accepts or emits keyword value names (§HC002). A
            plain identifier resolves through vocab_calls to its vocabulary's base-type names; a
            `|` union of vocabularies resolves to the union of each operand's names; an operand
            naming no local vocabulary contributes nothing. A value of any other shape names no
            type here."""
            if arg is None:
                return set()
            if arg.type == "identifier":
                vocab_call = vocab_calls.get(arg.text.decode("utf-8"))
                if vocab_call is None:
                    return set()
                base_names, _composed, _requires, _captures = vocabulary_types(ctx, vocab_call)
                return base_names
            if arg.type == "binary_operator":
                return vocab_arg_type_names(
                    arg.child_by_field_name("left")
                ) | vocab_arg_type_names(arg.child_by_field_name("right"))
            return set()

        def link_call_of(fdef):
            """The `@link(...)` call node decorating a function, or None when its @link is bare
            (`@link` with no call) — the decorator call HC002 reads accepts and emits from. Its
            callers pass only link-decorated functions (link_defs is built from is_link_decorated),
            so a `@link` decorator is always present; the one real None is the bare @link."""
            decorator = next(
                d for d in decorators_of(ctx, fdef) if decorator_target(d) == "link"
            )
            expr = decorator_expression(decorator)
            return expr if expr.type == "call" else None

        def seam_types(fdef, keyword):
            """The base-type names a link's @link decorator declares for one keyword (accepts
            or emits), or the empty set when the link declares none honest-check can resolve."""
            link_call = link_call_of(fdef)
            if link_call is None:
                return set()
            _positionals, keywords = call_arguments(ctx, link_call)
            return vocab_arg_type_names(keywords.get(keyword))

        link_defs = {}
        for node in nodes:
            if node.type != "function_definition":
                continue
            name_node = node.child_by_field_name("name")
            if name_node is None or not is_link_decorated(ctx, node):
                continue
            link_defs[name_node.text.decode("utf-8")] = node

        findings = []
        for node in nodes:
            if node.type != "call" or canonical_name(ctx, node) != "chain":
                continue
            positionals, _keywords = call_arguments(ctx, node)
            resolved = [
                link_defs.get(argument.text.decode("utf-8"))
                if argument.type == "identifier"
                else None
                for argument in positionals
            ]
            for i in range(1, len(resolved)):
                previous, current = resolved[i - 1], resolved[i]
                if previous is None or current is None:
                    continue
                missing = seam_types(current, "accepts") - seam_types(previous, "emits")
                if not missing:
                    continue
                name_node = current.child_by_field_name("name")
                name = name_node.text.decode("utf-8")
                findings.append(
                    diagnostic(ctx,
                        "HC002",
                        "error",
                        f"Chain link {name!r} accepts types the previous link does not emit: "
                        f"{sorted(missing)}. Change this link's accepts, change the previous "
                        "link's emits, or insert a link between them that produces the types.",
                        node,
                    )
                )
        return findings

    def check_hf001():
        """HC-HF001: a `feature_state(state, "flag")` call whose flag is not a key of the
        module's FEATURES vocabulary — an undeclared flag that raises KeyError at runtime (§7).
        Reported at the call's line. When FEATURES is not a readable module-scope dict literal
        the vocabulary is empty and the rule fires nothing."""
        features = features_vocabulary(ctx)
        if not features:
            return []
        findings = []
        for node in nodes:
            if node.type != "call":
                continue
            flag = feature_state_flag(ctx, node)
            if flag is None or flag in features:
                continue
            findings.append(
                diagnostic(ctx,
                    "HC-HF001",
                    "error",
                    f"feature_state references {flag!r}, which is not a declared flag in "
                    "FEATURES.",
                    node,
                )
            )
        return findings

    def check_hf002():
        """HC-HF002: a handler-table dispatch `TABLE[feature_state(state, "flag")]` whose table
        dict literal is missing an entry for one of the flag's FEATURES-declared states — that
        state raises KeyError when the flag enters it (§7). The subscript's index is a
        feature_state call naming a declared flag, and its object is a module-scope name bound
        to a dict literal. Reported at the subscript's line. When FEATURES is not a readable
        module-scope dict literal, or the table resolves to no module-scope dict literal, the
        rule fires nothing."""
        features = features_vocabulary(ctx)
        if not features:
            return []
        tables = module_dict_literals(ctx)
        findings = []
        for node in nodes:
            if node.type != "subscript":
                continue
            obj = node.child_by_field_name("value")
            index = node.child_by_field_name("subscript")
            if obj is None or index is None or obj.type != "identifier":
                continue
            if index.type != "call":
                continue
            flag = feature_state_flag(ctx, index)
            if flag is None or flag not in features:
                continue
            table = tables.get(obj.text.decode("utf-8"))
            if table is None:
                continue
            missing = features[flag] - table
            if not missing:
                continue
            findings.append(
                diagnostic(ctx,
                    "HC-HF002",
                    "warning",
                    f"Handler table {obj.text.decode('utf-8')!r} dispatched on feature "
                    f"{flag!r} has no entry for state(s) {sorted(missing)}; the flag entering "
                    "that state raises KeyError. Add the missing entry, or handle the state.",
                    node,
                )
            )
        return findings
    def check_p019():
        """HC-P019: a lookup read with a fallback default (§HC-P019). An attribute call named
        'get' or 'pop' with two or more positional arguments hands the second argument back for
        any key the table does not hold, so an unknown key is served as a known one and the miss
        is lost. Give the absent case its own row, or read without a fallback and report the miss."""
        findings = []
        for node in nodes:
            if node.type != "call":
                continue
            function = node.child_by_field_name("function")
            if function is None or function.type != "attribute":
                continue
            attr = function.child_by_field_name("attribute")
            if attr is None or attr.text.decode("utf-8") not in ("get", "pop"):
                continue
            positionals, _keywords = call_arguments(ctx, node)
            if len(positionals) < 2:
                continue
            findings.append(
                diagnostic(ctx,
                    "HC-P019",
                    "error",
                    "This lookup falls back to a default for a key the table does not hold, so "
                    "an unknown key is served as a known one and the miss is lost. If the absent "
                    "case is real, give it its own row with its own key. If the key can be "
                    "unknown, read without a fallback and report the miss, naming the expected keys.",
                    node,
                )
            )
        return findings

    def check_p020():
        """HC-P020: a dispatch read with no reported miss (§HC-P020). A subscript on a name bound
        to a module-scope dict literal, indexed by a variable, with no `key in TABLE` guard in the
        enclosing function, raises a bare KeyError for an unknown key and names neither the
        expected keys nor a fault. A constant key is a fixed row and is left alone."""
        tables = set(module_dict_literals(ctx))

        def guarded(function, key, table):
            lo, hi = function.start_byte, function.end_byte
            for candidate in nodes:
                if candidate.type != "comparison_operator":
                    continue
                if candidate.start_byte < lo or candidate.end_byte > hi:
                    continue
                if not any(child.type in ("in", "not in") for child in candidate.children):
                    continue
                names = {c.text.decode("utf-8") for c in candidate.named_children if c.type == "identifier"}
                if key in names and table in names:
                    return True
            return False

        findings = []
        for node in nodes:
            if node.type != "subscript":
                continue
            value = node.child_by_field_name("value")
            if value is None or value.type != "identifier":
                continue
            table = value.text.decode("utf-8")
            if table not in tables:
                continue
            index = node.child_by_field_name("subscript")
            if index is None or index.type != "identifier":
                continue
            parent = node.parent
            if parent is not None and parent.type in ("assignment", "augmented_assignment") \
                    and parent.child_by_field_name("left") is node:
                continue
            key = index.text.decode("utf-8")
            function = enclosing_function(node)
            if function is not None and guarded(function, key, table):
                continue
            findings.append(
                diagnostic(ctx,
                    "HC-P020",
                    "error",
                    "This dispatch read raises a bare KeyError for a key the table does not hold, "
                    "naming neither the expected keys nor a fault. Guard it with 'if key not in "
                    "TABLE' that reports the miss and names the expected keys, or give the absent "
                    "case its own row.",
                    node,
                )
            )
        return findings

    def check_p018():
        """HC-P018: a call whose target set is provably unbounded (§HC-P018). Only the proven
        cases are rejected: a bare `eval`/`exec` call runs arbitrary code, and a
        `getattr(obj, name)(...)` whose attribute name is not a string literal selects the callee
        from an unbounded name, so the call graph is infinite and cannot be exhaustively tested.
        A bounded form (a declared dict dispatch table, a getattr with a literal name, a callable
        parameter) is left alone; an import-produced callable needs dataflow to prove and is
        treated as undetermined rather than guessed."""
        findings = []
        for node in nodes:
            if node.type != "call":
                continue
            function = node.child_by_field_name("function")
            if function is None:
                continue
            if function.type == "identifier" and function.text.decode("utf-8") in ("eval", "exec"):
                findings.append(
                    diagnostic(ctx,
                        "HC-P018",
                        "error",
                        "This call runs code chosen at runtime, so the set of functions it may "
                        "invoke is open and the call graph is infinite. Use a declared dict "
                        "dispatch table (HC-P001), or pass the callable as a parameter from a "
                        "fixed set of call sites.",
                        node,
                    )
                )
                continue
            if function.type == "call":
                inner = function.child_by_field_name("function")
                if inner is None or inner.type != "identifier" or inner.text.decode("utf-8") != "getattr":
                    continue
                positionals, _keywords = call_arguments(ctx, function)
                if len(positionals) >= 2 and positionals[1].type != "string":
                    findings.append(
                        diagnostic(ctx,
                            "HC-P018",
                            "error",
                            "This call selects its target by a runtime attribute name, so the set "
                            "of functions it may invoke is not bounded to a finite, "
                            "statically-visible set and the call graph is infinite. Use a declared "
                            "dict dispatch table (HC-P001), or a getattr with a literal name.",
                            node,
                        )
                    )
        return findings

    per_file_rules = (
        check_classes,
        check_p001,
        check_p007,
        check_p011,
        check_p016,
        check_p002,
        check_p004,
        check_st001,
        check_p005,
        check_p006,
        check_p015,
        check_p010,
        check_p013,
        check_p018,
        check_p019,
        check_p020,
        check_hc008,
        check_hc001,
        check_hc002,
        check_hc_or001,
        check_hc_or003,
        check_p017,
        check_hc004,
        check_hc005,
        check_hc010,
        check_hf001,
        check_hf002,
    )
    diagnostics = []
    for rule in per_file_rules:
        diagnostics.extend(rule())
    return diagnostics
