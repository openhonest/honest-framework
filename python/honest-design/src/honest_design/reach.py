"""What each of a module's doors touches, directly and through a seam.

Asked, never asserted. This is the information half of a proposal to budget the I/O a chain
reaches, with the obligation half dropped (ruled 6 October 2026). The seam is the boundary of
responsibility: what happens past a door is the callee's declaration and the callee answers for
it, so nothing here accumulates into a number anyone owns. There is no verdict, no threshold, no
comparison against a previous run, and nothing of this is in any gate.

It says what it could not see. A count over declared seams counts what has been written down, and
the framework had 74 seams in its code with one declared, so an answer that hid its own blind
spots would read as a small reach when it is a small declaration.
"""

_OWN = ("env:", "store:")

# "caller" names the direction a call arrived from, not a thing the path touches. A door says it
# reads its caller, which is true and is never an answer to "what does this reach": past a seam
# the caller is the module that asked, and on the near side it is whoever called us. It is left
# out of both halves rather than reported as a side of the world reached.
_DIRECTION = frozenset({"caller"})


def _world(function, modules) -> set:
    """The sides of the world a function touches directly.

    Not a seam, not its own env or store, and not the direction its call came from. A target that
    is a module's name is a seam at module granularity and not a side of the world wearing a
    module's name: counting it as one answered that nothing was unfollowed for a seam nothing
    followed, which is the false comfort the unfollowed count exists to prevent.
    """
    return {
        side["target"]
        for side in function["side_effects"]
        if not side["module"] and not side["target"].startswith(_OWN)
        and side["target"] not in _DIRECTION and side["target"] not in modules
    }


def _seams(function, modules) -> list:
    """Every side of a function that enters another module, as (module, door).

    `door` is "" when the side names a module and no door. The door is what a side may add, never
    what it must, and the surface has listed modules since before the dot existed, so every seam
    declared before then is this shape.
    """
    return [
        (side["module"] or side["target"], side["door"])
        for side in function["side_effects"]
        if side["module"] or side["target"] in modules
    ]


def _onward(module) -> dict:
    """Who each function hands on to: its `invokes`, and the next link of any chain it is on.

    A door hands its input to one orchestrator written as a chain or as an `invokes`, and the
    method allows either, so a path written as a chain is a path. Reading only `invokes` answered
    that honest-parse's door touches nothing, when it reaches tree-sitter through its chain.
    """
    onward = {f["name"]: list(f["invokes"]) for f in module["functions"]}
    for chain in module["chains"]:
        for here, nxt in zip(chain["links"], chain["links"][1:]):
            onward.setdefault(here, []).append(nxt)
    return onward


def _walk(module, start, declarations, seen):
    """Follow one path from `start`, answering (direct, through, unfollowed).

    `seen` is every (module, function) already walked, so a module calling back into one it has
    already entered answers once rather than forever.
    """
    functions = {f["name"]: f for f in module["functions"]}
    onward = _onward(module)
    direct, through, unfollowed, coarse = set(), set(), 0, 0
    frontier = [start]
    while frontier:
        name = frontier.pop()
        key = (module["name"], name)
        if key in seen or name not in functions:
            continue
        seen.add(key)
        function = functions[name]
        direct |= _world(function, declarations)
        frontier.extend(onward.get(name, []))
        for other, door in _seams(function, declarations):
            if other not in declarations:
                unfollowed += 1
                continue
            far = declarations[other]
            # A seam naming no door is followed into every door of that module, because the
            # declaration did not say which one. The answer is wider than the code and the count
            # beside it says so.
            doors = [door] if door else [f["name"] for f in far["functions"] if f["role"] == "boundary_in"]
            coarse += 0 if door else 1
            for entrance in doors:
                far_direct, far_through, far_unfollowed, far_coarse = _walk(far, entrance, declarations, seen)
                through |= far_direct | far_through
                unfollowed += far_unfollowed
                coarse += far_coarse
    return direct, through, unfollowed, coarse


def reach(module, declarations) -> dict:
    """For each door of `module`, what its path touches.

    `direct` is the sides of the world declared on the path itself. `through` is what the path
    reaches past a seam, which belongs to the module on the far side and is kept apart for that
    reason: a caller reaches what a callee does, it does not inherit it, and the two are never
    summed. `unfollowed` counts the seams whose module was not among `declarations`, because a
    seam nobody could follow is not a seam that touches nothing.
    """
    answer = {}
    for function in module["functions"]:
        if function["role"] != "boundary_in":
            continue
        direct, through, unfollowed, coarse = _walk(module, function["name"], declarations, set())
        answer[function["name"]] = {
            "direct": sorted(direct),
            "through": sorted(through - direct),
            "unfollowed": unfollowed,
            "without_a_door": coarse,
        }
    return answer
