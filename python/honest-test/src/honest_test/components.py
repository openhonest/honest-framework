"""Component isolation tests (spec section 7).

Each check reads the minimal Component subset — name, template, routes — and returns Finding
records, empty when the components are isolated. The CSS and route checks are pure; the startup
check drives an injected loader and only observes which loads then fail.
"""

import re

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
    if not shared:
        return []
    names = ", ".join(sorted(shared))
    return [_finding(
        "failure", "css_namespace_collision",
        f"components {component_a['name']!r} and {component_b['name']!r} share CSS class names: {names}")]


def test_route_isolation(components):
    """Report route_collision when two components define the same path (spec section 7.2): one
    failure per collided path, naming both components. Reads no world, returns pure data."""
    findings = []
    owner = {}
    for component in components:
        for route in component["routes"]:
            path = route["path"]
            if path in owner:
                findings.append(_finding(
                    "failure", "route_collision",
                    f"route {path!r} is defined by both {owner[path]!r} and {component['name']!r}"))
            else:
                owner[path] = component["name"]
    return findings


# honest: disable HC-P002: the startup check's whole purpose is to observe a load failure (spec
# section 7.3); load_component is the injected effect, and catching its raise is how honest-test
# reads which components then fail — the failure is turned into a Finding, never swallowed.
def test_startup_isolation(components, load_component):
    """Report startup_cascade when one component's load failure breaks another (spec section
    7.3). The injected loader drives the genuine load; honest-test only observes which loads then
    fail."""
    findings = []
    for component in components:
        try:
            load_component(component)
        except Exception:
            for other in [other for other in components if other != component]:
                try:
                    load_component(other)
                except Exception:
                    findings.append(_finding(
                        "failure", "startup_cascade",
                        f"failure in {component['name']!r} caused failure in {other['name']!r}; "
                        "components must be independently loadable"))
    return findings
# honest: enable HC-P002
