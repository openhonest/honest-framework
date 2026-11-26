# scenario: _links selects direct top-level JavaScript link callbacks
# inherits: hd=python/honest-check/honest-check.hd::_links -> feature=specs/features/honest-check.feature::_links selects direct top-level JavaScript link callbacks

from honest_check import build_context
from honest_check.rules import _links


def probe_links_javascript_wrappers():
    source = b"""const first = link({}, () => Math.random());
const second = link({accepts: V}, function () { return process.env; });
function ordinary() { return process.env; }
const qualified = lib.link({}, () => process.env);
const referenced = link({}, ordinary);
const wrapped = outer(link({}, () => process.env));
const nonliteral = link(metadata, () => process.env);
const boundary = link({boundary: true}, () => Math.random());
const explicit = link({boundary: false}, () => NotSelected.env);
const optional = link?.({}, () => NotSelected.optional);
const single = link({'boundary': false}, () => NotSelected.single);
const double = link({"boundary": true}, () => NotSelected.double);
const escaped = link({"b\\u006fundary": false}, () => NotSelected.escaped);
const comment = link(/* option */ {/* metadata */ label}, () => Allowed.shorthand);
const numeric = link({1: label}, () => Allowed.numeric);
const string = link({"label": label}, () => Allowed.string);
"""
    ctx = build_context(source, "case.js", {})
    if ctx["root"].has_error:
        return ["JavaScript callback fixture did not parse"]
    actual = [(node.type, node.text) for node in _links(ctx)]
    expected = [
        ("arrow_function", b"() => Math.random()"),
        ("function_expression", b"function () { return process.env; }"),
        ("arrow_function", b"() => Allowed.shorthand"),
        ("arrow_function", b"() => Allowed.numeric"),
        ("arrow_function", b"() => Allowed.string"),
    ]
    return [] if actual == expected else [f"recognized JavaScript callbacks {actual!r}, expected {expected!r}"]
