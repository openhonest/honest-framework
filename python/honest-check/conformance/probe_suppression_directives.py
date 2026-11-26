# scenario: _directives retains the ranges each recognized directive owns
# inherits: hd=python/honest-check/honest-check.hd::_directives -> feature=specs/features/honest-check.feature::_directives retains the ranges each recognized directive owns


def probe_suppression_directives():
    from honest_check import build_context
    from honest_check.rules import _directives

    source = b"""# honest: disable HC-P004, HC-P005: reason
    # honest: disable HC-P004: redundant
    f()
    # honest: enable HC-P004
    g()  # honest: ignore HC-P011: reason
    """
    ctx = build_context(source, "case.py", {})
    actual = [
        (item.get("directive", {}).get("line"), item.get("directive", {}).get("verb"), {
            (span["rule"], span["first_line"], span["through_line"])
            for span in item.get("ranges", [])
        })
        for item in _directives(ctx)
    ]
    expected = [
        (1, "disable", {("HC-P004", 2, 3), ("HC-P005", 2, None)}),
        (2, "disable", set()),
        (4, "enable", set()),
        (5, "ignore", {("HC-P011", 5, 5)}),
    ]
    return [] if actual == expected else [f"owned ranges -> {actual!r}, expected {expected!r}"]
