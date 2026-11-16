"""Component isolation tests (spec section 7).

Each check reads the minimal Component subset — name, template, routes — and returns Finding
records, empty when the components are isolated. The CSS and route checks are pure; the startup
check drives an injected loader and only observes which loads then fail.
"""

import re

from honest_test._util import _pick
from honest_test.support import _finding

_CLASS_ATTR = re.compile(r'class\s*=\s*"([^"]*)"')


def extract_css_classes(template):
    """Pull the CSS class names out of a component's template (spec section 7.1). Reads no world,
    returns the set of class names."""
    classes = set()
    for group in _CLASS_ATTR.findall(template):
        classes.update(group.split())
    return classes


def test_css_isolation(component_a, component_b):
    """Report css_namespace_collision when two components share a CSS class (spec section 7.1):
    the finding names the shared classes. Reads no world, returns pure data."""
    shared = extract_css_classes(component_a["template"]) & extract_css_classes(component_b["template"])
    return _pick(
        bool(shared),
        lambda: [_finding(
            "failure", "css_namespace_collision",
            f"components {component_a['name']!r} and {component_b['name']!r} share CSS class names: "
            f"{', '.join(sorted(shared))}")],
        lambda: [],
    )


def test_route_isolation(components):
    """Report route_collision when two components define the same path (spec section 7.2): one
    failure per collided path, naming both components. Reads no world, returns pure data."""
    findings = []
    owner = {}
    for component in components:
        for route in component["routes"]:
            path = route["path"]
            _pick(
                path in owner,
                lambda: findings.append(_finding(
                    "failure", "route_collision",
                    f"route {path!r} is defined by both {owner[path]!r} and {component['name']!r}")),
                lambda: owner.__setitem__(path, component["name"]),
            )
    return findings


def test_startup_isolation(components, load_component):
    """Report startup_cascade when one component's load failure breaks another (spec section
    7.3). The injected loader drives the genuine load; honest-test only observes which loads then
    fail."""
    findings = []
    for component in components:
        try:  # honest: ignore HC-P002: the startup check observes a genuine load failure (spec 7.3); load_component is the injected effect and its raise becomes a Finding, never swallowed
            load_component(component)
        except Exception:
            others = filter(lambda other: other != component, components)
            for other in others:
                try:  # honest: ignore HC-P002: re-driving the injected loader to see whether one component's failure cascades into another is the check's purpose; the raise becomes a Finding
                    load_component(other)
                except Exception:
                    findings.append(_finding(
                        "failure", "startup_cascade",
                        f"failure in {component['name']!r} caused failure in {other['name']!r}; "
                        "components must be independently loadable"))
    return findings
