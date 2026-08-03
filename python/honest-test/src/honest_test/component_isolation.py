"""Component isolation tests (section 7): a component may not affect another's CSS namespace, route,
or ability to load.

A component is data: a name, its template (the HTML it renders), and its declared routes. The three
checks read that data and return findings - a shared CSS class between two components (section 7.1), a
route claimed by two components (section 7.2), or a component whose failure to load coincides with
another's (section 7.3). load is injected and returns a Result, so a failing load is data the check
reads, never an exception the interior catches.
"""

from honest_check.templates import template_class_references


def _finding(code, detail) -> dict:
    return {"code": code, "detail": detail}


def component_classes(template) -> frozenset:
    """The static CSS class tokens a component's template references (section 7.1). Interpolated class
    values are dynamic and skipped, exactly as honest-check's reference resolution skips them."""
    return frozenset(reference["class"] for reference in template_class_references(template))


def test_css_isolation(components) -> list:
    """Every pair of components must have disjoint CSS class names (section 7.1): a shared class means
    one component can restyle another, so each must namespace its classes under its own BEM block."""
    classes = [(component["name"], component_classes(component["template"])) for component in components]
    return [
        _finding("css_namespace_collision", {"components": [name_a, name_b], "classes": sorted(shared)})
        for index, (name_a, classes_a) in enumerate(classes)
        for name_b, classes_b in classes[index + 1:]
        for shared in [classes_a & classes_b]
        if shared
    ]


def test_route_isolation(components) -> list:
    """No two components may declare the same route path (section 7.2). The first component to claim a
    path owns it; a later component claiming it is a collision naming both."""
    findings = []
    owner = {}
    for component in components:
        for path in component["routes"]:
            if path in owner:
                findings.append(_finding("route_collision", {"path": path, "components": [owner[path], component["name"]]}))
                continue
            owner[path] = component["name"]
    return findings


def test_startup_isolation(components, load) -> list:
    """Components must be independently loadable (section 7.3): if one fails to load, every other must
    still load on its own. A component that also fails when loaded independently after another's
    failure is a cascade - the two are not isolated. load(component) returns ok or err."""
    findings = []
    failed = [component for component in components if "err" in load(component)]
    for component in failed:
        for other in components:
            if other["name"] == component["name"]:
                continue
            if "err" in load(other):
                findings.append(_finding("startup_cascade", {"failed": component["name"], "cascaded_to": other["name"]}))
    return findings
