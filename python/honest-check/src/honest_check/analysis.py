"""honest-check AST helper layer: analysis (split from core.py for L1.17).

Each helper takes the check context ctx (root, nodes, aliases, roles, source, path, rule_config)
and returns data; the rule logic that uses them stays nested-as-data in the sub-cores (section 3.4)."""

import ast
from honest_check.constants import _EMPTY_CONSTRUCTORS
from honest_check.nodes import call_arguments, called_name, canonical_name, decorator_expression, decorator_target, decorators_of, enclosing_function, is_attribute_suffix, is_keyword_name, link_locals, literal_string, own_body, string_members, watched


def dispatch_variable(ctx, condition):
    """The variable name an `if`/`elif` condition dispatches on — the left identifier of an
    `identifier == <value>` equality test — or None when the condition is not that shape
    (§HC-P001)."""
    if condition is None or condition.type != "comparison_operator":
        return None
    if not any(child.type == "==" for child in condition.children):
        return None
    operands = condition.named_children
    if len(operands) != 2 or operands[0].type != "identifier":
        return None
    return operands[0].text.decode("utf-8")


def within_class_init(ctx, node):
    """True when a node's nearest enclosing function is an `__init__` that is a method of a
    class — the scope HC-P007 reads for hidden instance state (§4.2)."""
    function = enclosing_function(node)
    if function is None:
        return False
    name = function.child_by_field_name("name")
    if name is None or name.text.decode("utf-8") != "__init__":
        return False
    grandparent = function.parent.parent if function.parent is not None else None
    return grandparent is not None and grandparent.type == "class_definition"


def mutated_names(ctx, statements):
    """The names an assignment or augmented assignment targets directly in a function
    body — the left of each `x = ...` or `x += ...` whose target is a plain identifier."""
    names = set()
    for statement in statements:
        if statement.type not in ("assignment", "augmented_assignment"):
            continue
        target = statement.child_by_field_name("left")
        if target is not None and target.type == "identifier":
            names.add(target.text.decode("utf-8"))
    return names


def is_empty_default(ctx, value):
    """True when a parameter's default stands for absence rather than a baked-in value
    (§HC-P015): None, False, a zero number, an empty string, an empty list/dict/tuple
    literal, or an empty-constructor call. A populated literal, a non-zero number, a
    non-empty string, True, a name or any other call is a real value and is not empty."""
    kind = value.type
    if kind in ("none", "false"):
        return True
    if kind in ("integer", "float"):
        return ast.literal_eval(value.text.decode("utf-8")) == 0
    if kind == "string":
        return not any(
            child.type in ("string_content", "interpolation")
            for child in value.named_children
        )
    if kind in ("list", "dictionary", "tuple"):
        return len(value.named_children) == 0
    if kind == "call":
        function = value.child_by_field_name("function")
        if function is None or function.type != "identifier":
            return False
        if function.text.decode("utf-8") not in _EMPTY_CONSTRUCTORS:
            return False
        positionals, keywords = call_arguments(ctx, value)
        return not positionals and not keywords
    return False


def dotted_target(ctx, call_node):
    """The dotted name a call invokes — `open`, `os.system`, `requests.get`,
    `urllib.request.urlopen` — or None when the target is not a plain or dotted name, such
    as a call on a call's result (§5.4)."""

    def name_of(node):
        if node.type == "identifier":
            return node.text.decode("utf-8")
        if node.type == "attribute":
            obj = name_of(node.child_by_field_name("object"))
            attr = node.child_by_field_name("attribute")
            if obj is None or attr is None:
                return None
            return f"{obj}.{attr.text.decode('utf-8')}"
        return None

    return name_of(call_node.child_by_field_name("function"))


def link_is_impure(ctx, fdef, watch, mutable_globals):
    """True when a link's own body calls a watched function or reads a module-level
    mutable global (§HC008). The body search does not descend into a nested def or
    lambda, whose statements are that inner scope's own."""
    body = own_body(fdef)
    locals_bound = link_locals(fdef, body)
    for node in body:
        if node.type == "call":
            target = dotted_target(ctx, node)
            if target is not None and watched(target, watch):
                return True
        elif node.type == "identifier":
            name = node.text.decode("utf-8")
            if (
                name in mutable_globals
                and name not in locals_bound
                and not is_attribute_suffix(node)
                and not is_keyword_name(node)
            ):
                return True
    return False


def is_link_decorated(ctx, fdef):
    """True when a function carries a `@link` decorator, bare or called — the chain-link
    declaration HC008 and HC001 both read for a declared link (§HC008, §4.2)."""
    return any(decorator_target(d) == "link" for d in decorators_of(ctx, fdef))


def local_function_links(ctx):
    """Each function defined in this file, mapped to whether it carries a `@link`
    decorator (§4.2, HC001). A chain positional that resolves to one of these names is a
    local link declaration honest-check can read; a name not here is defined elsewhere, so
    its declaration is invisible to honest-check and the positional is left alone."""
    nodes = ctx["nodes"]
    links = {}
    for node in nodes:
        if node.type != "function_definition":
            continue
        name_node = node.child_by_field_name("name")
        links[name_node.text.decode("utf-8")] = is_link_decorated(ctx, node)
    return links


def is_orchestrator(ctx, fdef):
    """True when a function carries an `@orchestrator` decorator, bare or called — matched
    by decorator name the same way a boundary decorator is (§4.2, HC-OR001)."""
    return any(decorator_target(d) == "orchestrator" for d in decorators_of(ctx, fdef))


def longest_shared_run(ctx, calls_a, calls_b):
    """The length of the longest run of consecutive equivalent call names two call
    sequences share (§HC-OR003). A contiguous common substring over the two lists, found
    by the standard row-by-row dynamic program; 0 when they share no adjacent run."""
    best = 0
    previous = [0] * (len(calls_b) + 1)
    for name_a in calls_a:
        current = [0] * (len(calls_b) + 1)
        for index, name_b in enumerate(calls_b, start=1):
            if name_a == name_b:
                current[index] = previous[index - 1] + 1
                if current[index] > best:
                    best = current[index]
        previous = current
    return best


def link_declares_emits(ctx, fdef):
    """True when a function carries a `@link` decorator that passes an `emits` keyword — the
    emits vocabulary HC-P017 requires of an HTTP-producing link (§HC-P017). Read the same
    way is_boundary_decorator reads `boundary`: from the decorator call's keyword
    arguments. A bare `@link` with no call declares no emits."""
    for decorator in decorators_of(ctx, fdef):
        if decorator_target(decorator) != "link":
            continue
        expr = decorator_expression(decorator)
        if expr.type != "call":
            continue
        _positionals, keywords = call_arguments(ctx, expr)
        if "emits" in keywords:
            return True
    return False


def construction_maps(ctx):
    """Each file-local variable bound to a `vocabulary(...)` or a `binding(...)` call,
    mapped to that construction call node (§HC004, §HC005). A name bound to anything else
    is not here; a name honest-check cannot resolve to one of these two constructions is
    one it cannot cross, and a pairing site naming it is left alone."""
    nodes = ctx["nodes"]
    vocab_calls = {}
    binding_calls = {}
    for node in nodes:
        if node.type != "assignment":
            continue
        left = node.child_by_field_name("left")
        right = node.child_by_field_name("right")
        if left is None or right is None or left.type != "identifier":
            continue
        if right.type != "call":
            continue
        canonical = canonical_name(ctx, right)
        name = left.text.decode("utf-8")
        if canonical == "vocabulary":
            vocab_calls[name] = right
        elif canonical == "binding":
            binding_calls[name] = right
    return vocab_calls, binding_calls


def features_vocabulary(ctx):
    """The feature-flag vocabulary this module declares: each flag name mapped to the set
    of states its `FEATURES[flag]["states"]` set names (§7, HC-HF001/HC-HF002). Read only
    from a module-scope `FEATURES = {...}` dict literal — the same top-level-assignment
    walk module_mutable_globals uses. Absent such a literal, an empty map, so both
    feature-flag rules have nothing to verify against and fire nothing (the spec's 'IF
    features is empty: RETURN')."""
    root = ctx["root"]
    for top in root.named_children:
        node = top
        if top.type == "expression_statement" and top.named_children:
            node = top.named_children[0]
        if node.type != "assignment":
            continue
        left = node.child_by_field_name("left")
        right = node.child_by_field_name("right")
        if left is None or right is None or left.type != "identifier":
            continue
        if left.text.decode("utf-8") != "FEATURES" or right.type != "dictionary":
            continue
        features = {}
        for pair in right.named_children:
            if pair.type != "pair":
                continue
            key = pair.child_by_field_name("key")
            if key is None or key.type != "string":
                continue
            value = pair.child_by_field_name("value")
            states = set()
            if value is not None and value.type == "dictionary":
                for inner in value.named_children:
                    if inner.type != "pair":
                        continue
                    inner_key = inner.child_by_field_name("key")
                    if inner_key is None or inner_key.type != "string":
                        continue
                    if literal_string(inner_key) != "states":
                        continue
                    inner_value = inner.child_by_field_name("value")
                    if inner_value is not None and inner_value.type == "set":
                        states = set(string_members(ctx, inner_value))
            features[literal_string(key)] = states
        return features
    return {}


def feature_state_flag(ctx, call_node):
    """The flag a `feature_state(state, "flag")` call names — its second positional, a
    string literal — or None when the call names fewer than two positionals or a dynamic
    (non-literal) flag (§7). The call is resolved by name through called_name."""
    if called_name(ctx, call_node) != "feature_state":
        return None
    positionals, _keywords = call_arguments(ctx, call_node)
    if len(positionals) < 2 or positionals[1].type != "string":
        return None
    return literal_string(positionals[1])


def module_dict_literals(ctx):
    """Each module-scope name bound to a dict literal, mapped to the set of string keys the
    literal declares (§7, HC-HF002). A name bound to anything but a module-scope dict
    literal is not here, so a handler table that resolves to no such name is skipped."""
    root = ctx["root"]
    tables = {}
    for top in root.named_children:
        node = top
        if top.type == "expression_statement" and top.named_children:
            node = top.named_children[0]
        if node.type != "assignment":
            continue
        left = node.child_by_field_name("left")
        right = node.child_by_field_name("right")
        if left is None or right is None or left.type != "identifier":
            continue
        if right.type != "dictionary":
            continue
        keys = set()
        for pair in right.named_children:
            if pair.type != "pair":
                continue
            key = pair.child_by_field_name("key")
            if key is not None and key.type == "string":
                keys.add(literal_string(key))
        tables[left.text.decode("utf-8")] = keys
    return tables
