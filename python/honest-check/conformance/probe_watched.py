"""Honest probe for honest-check's watched (Scenario: watched).

watched returns true when a call's dotted target is on the watch list: an exact
entry matches by equality, and an entry carrying a `*` matches as a glob — a
trailing `.*` names any attribute of a module, a trailing `*` is a prefix, and a
`*` between dots is one segment. The cases parse real calls with honest-parse,
hand the real dotted-target node (the call's `function` child) and a real watch
set to the function, and pin the boolean it must return for each matching rule
the scenario names.
"""

from honest_parse import parse, walk


def _call_target(source):
    root = parse(source.encode("utf-8"), "python").root_node
    for node in walk(root):
        if node.type == "call":
            return node.child_by_field_name("function")
    return None


# Each case: a call source (its dotted target is what watched reads), the watch
# set, and whether that target is watched.
_CASES = [
    {"src": "os.system(a)", "watch": {"os.system"}, "expect": True},                # exact match
    {"src": "os.system(a)", "watch": {"os.remove"}, "expect": False},               # exact miss
    {"src": "os.system(a)", "watch": {"os.*"}, "expect": True},                      # trailing .* : any attr of module os
    {"src": "os.system(a)", "watch": {"shutil.*"}, "expect": False},                # .* on a different module misses
    {"src": "requests.get(u)", "watch": {"requests*"}, "expect": True},             # trailing * : prefix
    {"src": "flask.get(u)", "watch": {"requests*"}, "expect": False},               # prefix miss
    {"src": "urllib.request.urlopen(u)", "watch": {"urllib.*.urlopen"}, "expect": True},  # * between dots : one segment
    {"src": "open(f)", "watch": {"os.system"}, "expect": False},                    # unrelated target, not watched
]


def probe_watched():
    """watched is true exactly when a call's dotted target matches a watch entry."""
    try:
        from honest_check import watched
    except ImportError as exc:
        return [f"cannot import watched: {exc}"]

    bad = []
    for case in _CASES:
        target = _call_target(case["src"])
        if target is None:
            bad.append(f"test setup: no call target in {case['src']!r}")
            continue
        got = watched(target, case["watch"])
        if got != case["expect"]:
            bad.append(
                f"watched({case['src']!r}, {case['watch']!r}) -> {got!r}, "
                f"expected {case['expect']!r}"
            )
    return bad
