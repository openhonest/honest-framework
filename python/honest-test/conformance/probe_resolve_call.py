"""Honest probe for honest-test's resolve_call (feature Scenario: resolve_call
resolves one suite case into a runnable ResolvedCall).

resolve_call is the pure first half of the value oracle. It resolves the function
name and each portable argument against the map — a literal is itself, a $ref is
looked up to its callable — and resolves the expected value the same way,
returning a ResolvedCall carrying the concrete callable, the resolved arguments,
and the resolved expected value. It returns a honest-test Fault when any name or
expression is not in the map, and it runs no code: resolution only reads the map
(.hd resolve_call; architecture section 8.6).

The probe asserts: a resolvable case yields a ResolvedCall whose function is the
concrete callable and whose $ref argument resolved to its callable; a $ref nested
inside a list argument (a chain's links list) and inside a dict argument both
resolve to the one shared object the name is bound to, so two cases naming it
resolve to the identical callable and that callable is usable downstream the way
execute_chain applies a link; an unresolvable name yields a honest-test Fault; and
resolution runs no code — a recording function named in the map is never called by
resolve_call.
"""

from honest_test import resolve_call


def _is_ht_fault(result):
    return isinstance(result, dict) and "problem" in result and "remedy" in result


def _is_resolved_call(result):
    return isinstance(result, dict) and "function" in result and "problem" not in result


def _add(a, b):
    """A real pure function under test: it returns the sum of its two inputs."""
    return a + b


def _square(n):
    """A real pure function a $ref argument names, so a function is reachable by name."""
    return n * n


def _shared_link(manifest):
    """A real callable a $ref names, applied downstream the way execute_chain applies a link."""
    return {**manifest, "seen": True}


def _run_first(links, manifest):
    """A fixture whose first positional argument is a links list; it applies the first link."""
    return links[0](manifest)


def probe_resolve_call():
    """resolve_call resolves names and literals into a runnable ResolvedCall,
    faults on an unknown name, and runs no code during resolution."""
    bad = []

    calls = []

    def _recording_square(n):
        """A real function that records each call, to witness that resolution runs no code."""
        calls.append(n)
        return n * n

    function_map = {"add": _add, "square": _square, "recording": _recording_square}

    resolved = resolve_call({"function": "add", "args": [2, {"$ref": "square"}], "expected": 7}, function_map)
    if not _is_resolved_call(resolved):
        bad.append(f"a resolvable case should resolve to a ResolvedCall, got {resolved!r}")
    else:
        if resolved.get("function") is not _add:
            bad.append(f"the ResolvedCall's function should be the callable 'add' named, got {resolved.get('function')!r}")
        args = resolved.get("args")
        if not (isinstance(args, list) and len(args) == 2):
            bad.append(f"the ResolvedCall should carry the two resolved arguments, got {args!r}")
        else:
            if args[0] != 2:
                bad.append(f"a literal argument should resolve to itself, got {args[0]!r}")
            if args[1] is not _square:
                bad.append(f"a $ref argument should resolve to its callable, got {args[1]!r}")
        if resolved.get("expected") != 7:
            bad.append(f"the expected value should resolve to itself, got {resolved.get('expected')!r}")

    # A $ref resolves to the one shared object its name is bound to wherever it appears:
    # nested inside a list argument (a chain's links list) and inside a dict argument, not
    # only at the top level. Two cases naming it resolve to the identical callable, and that
    # callable is usable downstream the way execute_chain applies a link.
    link_map = {"run_first": _run_first, "link": _shared_link}

    nested_list = resolve_call({"function": "run_first", "args": [[{"$ref": "link"}], {"x": "1"}], "expected": {"x": "1", "seen": True}}, link_map)
    if not _is_resolved_call(nested_list):
        bad.append(f"a case with a $ref nested in a list should resolve to a ResolvedCall, got {nested_list!r}")
    else:
        links = nested_list.get("args", [None])[0]
        if not (isinstance(links, list) and len(links) == 1 and links[0] is _shared_link):
            bad.append(f"a $ref nested in a list argument should resolve to its shared callable, got {links!r}")
        elif links[0]({"x": "1"}) != {"x": "1", "seen": True}:
            bad.append("the callable a nested $ref resolves to should be usable downstream as a link")

    nested_dict = resolve_call({"function": "run_first", "args": [{"links": {"$ref": "link"}}], "expected": None}, link_map)
    if _is_resolved_call(nested_dict) and nested_dict.get("args", [{}])[0].get("links") is not _shared_link:
        bad.append(f"a $ref nested in a dict argument should resolve to its shared callable, got {nested_dict.get('args')!r}")

    again = resolve_call({"function": "run_first", "args": [[{"$ref": "link"}], {}], "expected": {"seen": True}}, link_map)
    if _is_resolved_call(nested_list) and _is_resolved_call(again):
        if nested_list["args"][0][0] is not again["args"][0][0]:
            bad.append("two cases naming one value should resolve to the same shared object")

    unknown = resolve_call({"function": "multiply", "args": [2, 3], "expected": 6}, function_map)
    if not _is_ht_fault(unknown):
        bad.append(f"a case naming a symbol the map does not hold should return a honest-test Fault, got {unknown!r}")

    resolve_call({"function": "recording", "input": 4, "expected": 16}, function_map)
    if calls:
        bad.append(f"resolve_call must run no code, but the function under test was called with {calls!r}")

    return bad


def run():
    messages = probe_resolve_call()
    for message in messages:
        print(f"FAIL HT-probe [resolve_call]: {message}")
    passed = 0 if messages else 1
    print(f"resolve_call: {passed} passed, {len(messages)} failed")
    return 0 if not messages else 1


if __name__ == "__main__":
    raise SystemExit(run())
