"""The §8.4 protocol-level assertion library (honest-test.hd, type Response / Cookie / Finding).

Fourteen pure Then-step assertions over honest-test's own neutral Response record. Each reads
one field off the response, compares it to the value its step captured, and returns a list of
Finding: the empty list when the property holds, or exactly one failure Finding naming the field
and the two values when it does not. The record names no web framework type, so the same steps
run against any app (spec section 8.4).
"""

import json
from html.parser import HTMLParser

from honest_test._util import _choose, _pick, _read_or
from honest_test.support import _finding


# ---- the one failure Finding every assertion returns on a violation -------------------------

def _failure(code, message):
    """One failure Finding carrying a §8.4 FindingCode and a sentence naming the field and the
    two values (honest-test.hd, type Finding). location is empty: a run-time check points at no
    source line."""
    return [_finding("failure", code, message)]


# ---- status ---------------------------------------------------------------------------------

def assert_status(response, status):
    """Empty list when the response status equals status, else one status_mismatch failure."""
    actual = response["status"]
    return _pick(
        actual == status,
        lambda: [],
        lambda: _failure("status_mismatch", f"response status: expected {status}, got {actual}"),
    )


def assert_status_class(response, status_class):
    """Empty list when the response status falls in the asserted 2xx/3xx/4xx/5xx band, else one
    status_class_mismatch failure. The band the status sits in is computed from the status
    itself and compared, so no open-input lookup is read."""
    actual = response["status"]
    actual_class = f"{actual // 100}xx"
    return _pick(
        actual_class == status_class,
        lambda: [],
        lambda: _failure(
            "status_class_mismatch",
            f"response status class: expected {status_class}, got {actual} ({actual_class})"),
    )


# ---- headers --------------------------------------------------------------------------------

def assert_content_type(response, mime_type):
    """Empty list when the response Content-Type equals mime_type, else one
    content_type_mismatch failure. An absent header resolves to None and fails the comparison."""
    actual = response["headers"].get("Content-Type")
    return _pick(
        actual == mime_type,
        lambda: [],
        lambda: _failure(
            "content_type_mismatch",
            f"response Content-Type: expected {mime_type!r}, got {actual!r}"),
    )


def assert_charset(response, charset):
    """Empty list when the response charset equals charset, else one charset_mismatch failure."""
    actual = response["charset"]
    return _pick(
        actual == charset,
        lambda: [],
        lambda: _failure("charset_mismatch", f"response charset: expected {charset!r}, got {actual!r}"),
    )


def assert_header(response, name, value):
    """Empty list when header name is present and equals value, else one header_mismatch
    failure. An absent header resolves to None and fails the comparison."""
    actual = response["headers"].get(name)
    return _pick(
        actual == value,
        lambda: [],
        lambda: _failure("header_mismatch", f"response header {name!r}: expected {value!r}, got {actual!r}"),
    )


def assert_no_header(response, name):
    """Empty list when header name is absent, else one header_present failure naming its value."""
    headers = response["headers"]
    return _pick(
        name not in headers,
        lambda: [],
        lambda: _failure(
            "header_present",
            f"response header {name!r}: expected absent, present with value {headers[name]!r}"),
    )


# ---- body -----------------------------------------------------------------------------------

def assert_body_bytes(response, literal):
    """Empty list when the response body equals literal exactly, else one body_bytes_mismatch
    failure."""
    actual = response["body"]
    return _pick(
        actual == literal,
        lambda: [],
        lambda: _failure("body_bytes_mismatch", f"response body bytes: expected {literal!r}, got {actual!r}"),
    )


# The JSON type keyword picks which shape the value must have — genuine dispatch, so a table of
# predicates keyed on the closed keyword, read through a no-match guard (honest-type-architecture
# §13.7, HC-P020). A boolean is not an integer or a number here: JSON distinguishes them.
_JSON_TYPE_CHECKS = {
    "object": lambda value: isinstance(value, dict),
    "array": lambda value: isinstance(value, list),
    "string": lambda value: isinstance(value, str),
    "integer": lambda value: isinstance(value, int) and not isinstance(value, bool),
    "number": lambda value: isinstance(value, (int, float)) and not isinstance(value, bool),
    "boolean": lambda value: isinstance(value, bool),
}


def _type_mismatch(value, expected_type, check):
    """A type-mismatch message when the value fails the known type's predicate (spec section 8.4)."""
    return _pick(check(value), lambda: [], lambda: [f"expected type {expected_type!r}, got {value!r}"])


def _known_or_unknown_type(value, expected_type):
    """A violation message for a declared type (spec section 8.4): unknown type when the schema
    names one outside the closed vocabulary, else a mismatch when the value fails its predicate."""
    check = _read_or(_JSON_TYPE_CHECKS, expected_type, None)
    return _pick(
        check is None,
        lambda: [f"schema names unknown type {expected_type!r}; accepted types are {sorted(_JSON_TYPE_CHECKS)}"],
        lambda: _type_mismatch(value, expected_type, check),
    )


def _type_violations(value, expected_type):
    """The type-constraint violations for a value (spec section 8.4); the empty list when the schema
    declares no type."""
    return _pick(expected_type is None, lambda: [], lambda: _known_or_unknown_type(value, expected_type))


def _required_violations(value, schema):
    """A missing-key message per declared required key the object lacks (spec section 8.4)."""
    missing = filter(lambda key: key not in value, _read_or(schema, "required", []))
    return [f"missing required key {key!r}" for key in missing]


def _property_violations(value, schema):
    """The violations for each declared property present on the object, recursing into its subschema
    (spec section 8.4)."""
    present = filter(lambda kv: kv[0] in value, _read_or(schema, "properties", {}).items())
    result = []
    for key, subschema in present:
        result.extend(_schema_violations(value[key], subschema))
    return result


def _object_violations(value, schema):
    """The required-key and property violations when the value is an object (spec section 8.4); the
    empty list otherwise."""
    return _pick(
        _JSON_TYPE_CHECKS["object"](value),
        lambda: _required_violations(value, schema) + _property_violations(value, schema),
        lambda: [],
    )


def _schema_violations(value, schema):
    """Violation messages for value against a JSON Schema subset (type, required, properties),
    recursing into properties. Empty list means the value conforms. Pure, raises nothing."""
    return _type_violations(value, schema.get("type")) + _object_violations(value, schema)


def _parse_json_body(body):
    """Return {"ok": True, "value": v} for parseable JSON, else {"ok": False, "reason": msg}.
    The absence of a parse is an explicit bounded case, resolved here and read by the caller."""
    try:  # honest: ignore HC-P002: json.loads is the one boundary where an unparseable body becomes data; the except turns the decode error into the bounded {"ok": False} case the schema check reads, keeping this function's "returns a Finding" contract so the interior validator never touches an exception
        return {"ok": True, "value": json.loads(body)}
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return {"ok": False, "reason": f"body is not valid JSON ({exc})"}


def _schema_result(parsed, schema):
    """The body_schema_violation Finding for a parseable body (spec section 8.4): the first
    nonconformance, or the empty list when the value conforms."""
    violations = _schema_violations(parsed["value"], schema)
    return _pick(
        bool(violations),
        lambda: _failure("body_schema_violation", f"response body: {violations[0]}"),
        lambda: [],
    )


def assert_body_json_schema(response, schema):
    """Empty list when the response body parses as JSON conforming to schema, else one
    body_schema_violation failure naming the first nonconformance (unparseable body, wrong type,
    or missing required key)."""
    parsed = _parse_json_body(response["body"])
    return _pick(
        not parsed["ok"],
        lambda: _failure("body_schema_violation", f"response body: {parsed['reason']}"),
        lambda: _schema_result(parsed, schema),
    )


# The CSS selector forms §8.4 supports map to a (tag, class, id) triple the element must match.
_SELECTOR_PREFIXES = {
    ".": lambda rest: (None, rest, None),
    "#": lambda rest: (None, None, rest),
}


def _split_tag_class(selector):
    """Parse a `tag.class` selector into its (tag, class, id) triple (spec section 8.4)."""
    tag, class_name = selector.split(".", 1)
    return (tag, class_name, None)


def _parse_tagged(selector):
    """Parse a selector with no recognised prefix (spec section 8.4): `tag.class`, else a bare tag."""
    return _pick("." in selector, lambda: _split_tag_class(selector), lambda: (selector, None, None))


def _parse_selector(selector):
    """Parse a supported selector into (tag, class, id): `div`, `.item`, `#main`, `li.item`."""
    head = selector[:1]
    prefix = _read_or(_SELECTOR_PREFIXES, head, None)
    return _pick(prefix is not None, lambda: prefix(selector[1:]), lambda: _parse_tagged(selector))


def _classes_of(attrs):
    """The CSS class names on a start tag's attributes, empty when it carries no class (section 8.4)."""
    return _read_or(attrs, "class", "").split()


def _element_matches(element, parsed):
    """True when a parsed start tag (tag, attrs dict) satisfies the (tag, class, id) triple."""
    want_tag, want_class, want_id = parsed
    tag, attrs = element
    tag_ok = want_tag is None or tag == want_tag
    id_ok = want_id is None or attrs.get("id") == want_id
    class_ok = want_class is None or want_class in _classes_of(attrs)
    return tag_ok and id_ok and class_ok


def _collect_start_tags(body):
    """Every start tag in body as (tag, attrs-dict) pairs, parsed by stdlib html.parser. The
    parser's handle_starttag is bound to a local collector so no subclass is declared."""
    elements = []
    parser = HTMLParser(convert_charrefs=True)
    parser.handle_starttag = lambda tag, attrs: elements.append(
        (tag, {name: _choose(value is None, "", value) for name, value in attrs})
    )
    parser.feed(body.decode("utf-8", "replace"))
    parser.close()
    return elements


def assert_body_html_selector(response, selector):
    """Empty list when the response body is HTML with at least one element the selector matches,
    else one body_selector_absent failure. Supports a tag, a class, an id, and a tag with a
    class."""
    parsed = _parse_selector(selector)
    elements = _collect_start_tags(response["body"])
    return _pick(
        any(_element_matches(element, parsed) for element in elements),
        lambda: [],
        lambda: _failure("body_selector_absent", f"response body: no element matches selector {selector!r}"),
    )


# ---- cookies --------------------------------------------------------------------------------

def _find_cookie(cookies, name):
    """The first cookie named name, or None when none is present."""
    matching = filter(lambda cookie: cookie["name"] == name, cookies)
    for cookie in matching:
        return cookie
    return None


def _cookie_value_result(cookie, name, value):
    """The cookie_value_mismatch Finding for a present cookie (spec section 8.4): empty when its
    value matches, else a mismatch naming both values."""
    return _pick(
        cookie["value"] == value,
        lambda: [],
        lambda: _failure(
            "cookie_value_mismatch",
            f"response cookie {name!r}: expected value {value!r}, got {cookie['value']!r}"),
    )


def assert_cookie_value(response, name, value):
    """Empty list when a cookie named name is set to value, else one cookie_value_mismatch
    failure naming the expected value and the actual value or the cookie's absence."""
    cookie = _find_cookie(response["cookies"], name)
    return _pick(
        cookie is None,
        lambda: _failure(
            "cookie_value_mismatch",
            f"response cookie {name!r}: expected value {value!r}, cookie absent"),
        lambda: _cookie_value_result(cookie, name, value),
    )


def _cookie_attribute_result(cookie, name, attribute):
    """The cookie_attribute_absent Finding for a present cookie (spec section 8.4): empty when it
    carries the attribute, else an absent failure."""
    return _pick(
        attribute in cookie["attributes"],
        lambda: [],
        lambda: _failure(
            "cookie_attribute_absent",
            f"response cookie {name!r}: expected attribute {attribute!r}, not present"),
    )


def assert_cookie_attribute(response, name, attribute):
    """Empty list when cookie name carries attribute, else one cookie_attribute_absent failure."""
    cookie = _find_cookie(response["cookies"], name)
    return _pick(
        cookie is None,
        lambda: _failure(
            "cookie_attribute_absent",
            f"response cookie {name!r}: expected attribute {attribute!r}, cookie absent"),
        lambda: _cookie_attribute_result(cookie, name, attribute),
    )


def _max_age_compare(attributes, name, max_age):
    """The cookie_max_age_mismatch Finding for a cookie carrying Max-Age (spec section 8.4): empty
    when it equals max_age, else a mismatch naming both."""
    actual = int(attributes["Max-Age"])
    return _pick(
        actual == max_age,
        lambda: [],
        lambda: _failure(
            "cookie_max_age_mismatch",
            f"response cookie {name!r}: expected Max-Age {max_age}, got {actual}"),
    )


def _max_age_present(cookie, name, max_age):
    """The cookie_max_age check for a present cookie (spec section 8.4): a no-Max-Age failure when it
    carries none, else the value comparison."""
    attributes = cookie["attributes"]
    return _pick(
        "Max-Age" not in attributes,
        lambda: _failure(
            "cookie_max_age_mismatch",
            f"response cookie {name!r}: expected Max-Age {max_age}, no Max-Age set"),
        lambda: _max_age_compare(attributes, name, max_age),
    )


def assert_cookie_max_age(response, name, max_age):
    """Empty list when cookie name's Max-Age equals max_age seconds, else one
    cookie_max_age_mismatch failure naming the expected and actual Max-Age or the absence."""
    cookie = _find_cookie(response["cookies"], name)
    return _pick(
        cookie is None,
        lambda: _failure(
            "cookie_max_age_mismatch",
            f"response cookie {name!r}: expected Max-Age {max_age}, cookie absent"),
        lambda: _max_age_present(cookie, name, max_age),
    )


# ---- location and session -------------------------------------------------------------------

def assert_location(response, url):
    """Empty list when the response Location equals url, else one location_mismatch failure."""
    actual = response["location"]
    return _pick(
        actual == url,
        lambda: [],
        lambda: _failure("location_mismatch", f"response location: expected {url!r}, got {actual!r}"),
    )


def _session_compare(current, earlier):
    """The session_cookie_mismatch Finding for two present session cookies (spec section 8.4): empty
    when their values match, else a mismatch naming both."""
    return _pick(
        current["value"] == earlier["value"],
        lambda: [],
        lambda: _failure(
            "session_cookie_mismatch",
            f"session cookie: expected one shared value, got {current['value']!r} "
            f"and {earlier['value']!r}"),
    )


def assert_same_session_cookie(response, previous):
    """Empty list when both responses set a cookie named 'session' to the same value, else one
    session_cookie_mismatch failure naming the two values or the absence."""
    current = _find_cookie(response["cookies"], "session")
    earlier = _find_cookie(previous["cookies"], "session")
    return _pick(
        current is None or earlier is None,
        lambda: _failure(
            "session_cookie_mismatch",
            f"session cookie: expected one shared value, present={current is not None}, "
            f"previous present={earlier is not None}"),
        lambda: _session_compare(current, earlier),
    )
