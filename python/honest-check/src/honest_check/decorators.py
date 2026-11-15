"""Decorator and boundary-scope reading (§4.2). A function's role, link and
emission declarations are read off its decorators; the interior-scope test HC-P002,
HC-P004 and HC-P005 fire in is read here too."""

from ._util import choose, pick, read_or
from .nodes import _field, _function_name, _text, bare_or_final_name

_DOOR_ROLES = {"boundary_in", "boundary_out", "reader"}


def decorators_of(ctx, fdef):
    """The decorator nodes applied to a function, or the empty list when it has
    none (§4.2)."""
    parent = fdef.parent
    decorated = bool(parent is not None and parent.type == "decorated_definition")
    return pick(
        decorated,
        lambda: [c for c in filter(lambda c: c.type == "decorator", parent.children)],
        lambda: [],
    )


def decorator_expression(decorator):
    """The expression a decorator applies — its first named child."""
    return decorator.named_children[0]


def decorator_target(decorator):
    """The final name a decorator names, or None when it is neither a plain nor a
    dotted name (§4.2)."""
    expr = decorator_expression(decorator)
    head = choose(expr.type == "call", _field(expr, "function"), expr)
    return bare_or_final_name(head)


def _keyword_value(decorator, name):
    """The source text of a decorator call's keyword argument `name`, or None when
    the decorator is not a call or carries no such keyword."""
    expr = decorator_expression(decorator)
    call = choose(expr.type == "call", expr, None)
    args = _field(call, "arguments")
    members = pick(args is None, lambda: [], lambda: list(args.named_children))
    kwarg = next(
        filter(
            lambda m: m.type == "keyword_argument"
            and _text(_field(m, "name")) == name,
            members,
        ),
        None,
    )
    return _text(_field(kwarg, "value"))


def is_boundary_decorator(ctx, decorator):
    """True when a decorator declares its function a boundary — @boundary (bare or
    called) or @link(boundary=True) (§4.2)."""
    target = decorator_target(decorator)
    return bool(
        target == "boundary"
        or (target == "link" and _keyword_value(decorator, "boundary") == "True")
    )


def has_decorator(ctx, fdef, name):
    """True when a function carries a decorator whose target is `name`, bare or
    called (§4.2)."""
    return any(decorator_target(d) == name for d in decorators_of(ctx, fdef))


def link_declares_emits(ctx, fdef):
    """True when a function carries a @link decorator passing an `emits` keyword
    (§HC-P017)."""
    return any(
        decorator_target(d) == "link" and _keyword_value(d, "emits") is not None
        for d in decorators_of(ctx, fdef)
    )


def _function_is_boundary(ctx, fdef):
    return any(is_boundary_decorator(ctx, d) for d in decorators_of(ctx, fdef))


def _declared_door(ctx, fdef):
    return read_or(ctx["roles"], _function_name(fdef), "") in _DOOR_ROLES


def in_non_boundary_function(ctx, node):
    """True when a node's nearest enclosing function exists, carries no boundary
    decorator, and the declaration gives its name no door role (§4.2)."""
    from .nodes import enclosing_function

    fn = enclosing_function(node)
    return bool(
        fn is not None
        and not _function_is_boundary(ctx, fn)
        and not _declared_door(ctx, fn)
    )
