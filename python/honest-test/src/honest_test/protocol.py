"""The §8.4 protocol-level assertion library (honest-test.hd, type Response / Cookie / Finding).

Fourteen pure Then-step assertions over honest-test's own neutral Response record. Each reads
one field off the response, compares it to the value its step captured, and returns a list of
Finding: the empty list when the property holds, or exactly one failure Finding naming the field
and the two values when it does not. The record names no web framework type, so the same steps
run against any app (spec section 8.4).
"""

import json
from html.parser import HTMLParser

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
    if actual == status:
        return []
    return _failure(
        "status_mismatch",
        f"response status: expected {status}, got {actual}",
    )


def assert_status_class(response, status_class):
    """Empty list when the response status falls in the asserted 2xx/3xx/4xx/5xx band, else one
    status_class_mismatch failure. The band the status sits in is computed from the status
    itself and compared, so no open-input lookup is read."""
    actual = response["status"]
    actual_class = f"{actual // 100}xx"
    if actual_class == status_class:
        return []
    return _failure(
        "status_class_mismatch",
        f"response status class: expected {status_class}, got {actual} ({actual_class})",
    )


# ---- headers --------------------------------------------------------------------------------

def assert_content_type(response, mime_type):
    """Empty list when the response Content-Type equals mime_type, else one
    content_type_mismatch failure. An absent header resolves to None and fails the comparison."""
    actual = response["headers"].get("Content-Type")
    if actual == mime_type:
        return []
    return _failure(
        "content_type_mismatch",
        f"response Content-Type: expected {mime_type!r}, got {actual!r}",
    )


def assert_charset(response, charset):
    """Empty list when the response charset equals charset, else one charset_mismatch failure."""
    actual = response["charset"]
    if actual == charset:
        return []
    return _failure(
        "charset_mismatch",
        f"response charset: expected {charset!r}, got {actual!r}",
    )


def assert_header(response, name, value):
    """Empty list when header name is present and equals value, else one header_mismatch
    failure. An absent header resolves to None and fails the comparison."""
    actual = response["headers"].get(name)
    if actual == value:
        return []
    return _failure(
        "header_mismatch",
        f"response header {name!r}: expected {value!r}, got {actual!r}",
    )


def assert_no_header(response, name):
    """Empty list when header name is absent, else one header_present failure naming its value."""
    headers = response["headers"]
    if name not in headers:
        return []
    return _failure(
        "header_present",
        f"response header {name!r}: expected absent, present with value {headers[name]!r}",
    )


# ---- body -----------------------------------------------------------------------------------

def assert_body_bytes(response, literal):
    """Empty list when the response body equals literal exactly, else one body_bytes_mismatch
    failure."""
    actual = response["body"]
    if actual == literal:
        return []
    return _failure(
        "body_bytes_mismatch",
        f"response body bytes: expected {literal!r}, got {actual!r}",
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


def _schema_violations(value, schema):
    """Violation messages for value against a JSON Schema subset (type, required, properties),
    recursing into properties. Empty list means the value conforms. Pure, raises nothing."""
    violations = []
    expected_type = schema.get("type")
    if expected_type is not None:
        if expected_type not in _JSON_TYPE_CHECKS:
            accepted = sorted(_JSON_TYPE_CHECKS)
            violations.append(
                f"schema names unknown type {expected_type!r}; accepted types are {accepted}"
            )
        elif not _JSON_TYPE_CHECKS[expected_type](value):
            violations.append(f"expected type {expected_type!r}, got {value!r}")
    if _JSON_TYPE_CHECKS["object"](value):
        if "required" in schema:
            for key in schema["required"]:
                if key not in value:
                    violations.append(f"missing required key {key!r}")
        if "properties" in schema:
            for key, subschema in schema["properties"].items():
                if key in value:
                    violations.extend(_schema_violations(value[key], subschema))
    return violations


# honest: disable HC-P002: json.loads is the one boundary where an unparseable body becomes data;
# the except turns the library's decode error into the body_schema_violation Finding the spec
# requires rather than letting it propagate, keeping this pure function's "returns a Finding"
# contract. The parse is isolated here so the interior validator never touches an exception.
def _parse_json_body(body):
    """Return {"ok": True, "value": v} for parseable JSON, else {"ok": False, "reason": msg}.
    The absence of a parse is an explicit bounded case, resolved here and read by the caller."""
    try:
        return {"ok": True, "value": json.loads(body)}
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return {"ok": False, "reason": f"body is not valid JSON ({exc})"}
# honest: enable HC-P002


def assert_body_json_schema(response, schema):
    """Empty list when the response body parses as JSON conforming to schema, else one
    body_schema_violation failure naming the first nonconformance (unparseable body, wrong type,
    or missing required key)."""
    parsed = _parse_json_body(response["body"])
    if not parsed["ok"]:
        return _failure("body_schema_violation", f"response body: {parsed['reason']}")
    violations = _schema_violations(parsed["value"], schema)
    if not violations:
        return []
    return _failure("body_schema_violation", f"response body: {violations[0]}")


# The CSS selector forms §8.4 supports map to a (tag, class, id) triple the element must match.
_SELECTOR_PREFIXES = {
    ".": lambda rest: (None, rest, None),
    "#": lambda rest: (None, None, rest),
}


def _parse_selector(selector):
    """Parse a supported selector into (tag, class, id): `div`, `.item`, `#main`, `li.item`."""
    head = selector[:1]
    if head in _SELECTOR_PREFIXES:
        return _SELECTOR_PREFIXES[head](selector[1:])
    if "." in selector:
        tag, class_name = selector.split(".", 1)
        return (tag, class_name, None)
    return (selector, None, None)


def _element_matches(element, parsed):
    """True when a parsed start tag (tag, attrs dict) satisfies the (tag, class, id) triple."""
    want_tag, want_class, want_id = parsed
    tag, attrs = element
    if want_tag is not None and tag != want_tag:
        return False
    if want_id is not None and attrs.get("id") != want_id:
        return False
    if want_class is not None:
        classes = attrs["class"].split() if "class" in attrs else []
        if want_class not in classes:
            return False
    return True


def _collect_start_tags(body):
    """Every start tag in body as (tag, attrs-dict) pairs, parsed by stdlib html.parser. The
    parser's handle_starttag is bound to a local collector so no subclass is declared."""
    elements = []
    parser = HTMLParser(convert_charrefs=True)
    parser.handle_starttag = lambda tag, attrs: elements.append(
        (tag, {name: ("" if value is None else value) for name, value in attrs})
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
    if any(_element_matches(element, parsed) for element in elements):
        return []
    return _failure(
        "body_selector_absent",
        f"response body: no element matches selector {selector!r}",
    )


# ---- cookies --------------------------------------------------------------------------------

def _find_cookie(cookies, name):
    """The first cookie named name, or None when none is present."""
    for cookie in cookies:
        if cookie["name"] == name:
            return cookie
    return None


def assert_cookie_value(response, name, value):
    """Empty list when a cookie named name is set to value, else one cookie_value_mismatch
    failure naming the expected value and the actual value or the cookie's absence."""
    cookie = _find_cookie(response["cookies"], name)
    if cookie is None:
        return _failure(
            "cookie_value_mismatch",
            f"response cookie {name!r}: expected value {value!r}, cookie absent",
        )
    if cookie["value"] == value:
        return []
    return _failure(
        "cookie_value_mismatch",
        f"response cookie {name!r}: expected value {value!r}, got {cookie['value']!r}",
    )


def assert_cookie_attribute(response, name, attribute):
    """Empty list when cookie name carries attribute, else one cookie_attribute_absent failure."""
    cookie = _find_cookie(response["cookies"], name)
    if cookie is None:
        return _failure(
            "cookie_attribute_absent",
            f"response cookie {name!r}: expected attribute {attribute!r}, cookie absent",
        )
    if attribute in cookie["attributes"]:
        return []
    return _failure(
        "cookie_attribute_absent",
        f"response cookie {name!r}: expected attribute {attribute!r}, not present",
    )


def assert_cookie_max_age(response, name, max_age):
    """Empty list when cookie name's Max-Age equals max_age seconds, else one
    cookie_max_age_mismatch failure naming the expected and actual Max-Age or the absence."""
    cookie = _find_cookie(response["cookies"], name)
    if cookie is None:
        return _failure(
            "cookie_max_age_mismatch",
            f"response cookie {name!r}: expected Max-Age {max_age}, cookie absent",
        )
    attributes = cookie["attributes"]
    if "Max-Age" not in attributes:
        return _failure(
            "cookie_max_age_mismatch",
            f"response cookie {name!r}: expected Max-Age {max_age}, no Max-Age set",
        )
    actual = int(attributes["Max-Age"])
    if actual == max_age:
        return []
    return _failure(
        "cookie_max_age_mismatch",
        f"response cookie {name!r}: expected Max-Age {max_age}, got {actual}",
    )


# ---- location and session -------------------------------------------------------------------

def assert_location(response, url):
    """Empty list when the response Location equals url, else one location_mismatch failure."""
    actual = response["location"]
    if actual == url:
        return []
    return _failure(
        "location_mismatch",
        f"response location: expected {url!r}, got {actual!r}",
    )


def assert_same_session_cookie(response, previous):
    """Empty list when both responses set a cookie named 'session' to the same value, else one
    session_cookie_mismatch failure naming the two values or the absence."""
    current = _find_cookie(response["cookies"], "session")
    earlier = _find_cookie(previous["cookies"], "session")
    if current is None or earlier is None:
        return _failure(
            "session_cookie_mismatch",
            f"session cookie: expected one shared value, present={current is not None}, "
            f"previous present={earlier is not None}",
        )
    if current["value"] == earlier["value"]:
        return []
    return _failure(
        "session_cookie_mismatch",
        f"session cookie: expected one shared value, got {current['value']!r} "
        f"and {earlier['value']!r}",
    )
