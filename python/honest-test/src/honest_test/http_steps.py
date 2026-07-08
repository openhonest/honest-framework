"""Standard protocol-level assertion steps (section 8.4): the HTTP step library every honest-test spoke
ships, so a developer asserts on the HTTP surface in a .feature file without extra scaffolding.

Auto-generation covers a chain at the manifest level; it does not see status codes, headers,
Content-Type, cookies, or body bytes — exactly the class of bug (a serializer emitting `text/plain`
instead of `text/html; charset=utf-8`) that passes chain-contract and honesty checks yet breaks every
client. These steps give feature authors a vocabulary for those properties.

Every handler is a pure (context, **captures) -> context wired through register_step — no decorators,
no mutable shared context. honest-test stays framework-agnostic: it reads a NORMALIZED response the app's
test client provides and sends through an injected client, never a specific web framework.

The context contract the application wires in:
  context["client"](method, path, request) -> response   — the injected test client
  request  = {"headers": {name: value}, "cookies": {name: value}, "body": bytes, "content_type": str}
  response = {"status": int, "headers": {lowercased-name: value}, "body": bytes,
              "cookies": {name: {"value": str, "attributes": {attr: value}}}}
  context["schemas"] = {name: (parsed_json -> bool)}   — named body-shape validators
The session cookie is named "session"; a when-step stores the prior response as context["previous_response"].
"""

import json
import re

from honest_gherkin import register_step
from honest_parse import node_text, parse_html, walk

_SESSION = "session"
_EMPTY_REQUEST = {"headers": {}, "cookies": {}, "body": b"", "content_type": None}


def _request(context):
    """The request being built in the context, or a fresh empty one."""
    return context.get("request", _EMPTY_REQUEST)


def _content_type(response):
    """The response Content-Type header value, or the empty string when absent."""
    return response["headers"].get("content-type", "")


def _mime(response):
    """The media type of the response — the Content-Type before any parameters."""
    return _content_type(response).split(";")[0].strip()


def _charset(response):
    """The charset parameter of the response Content-Type, or the empty string when absent."""
    for part in _content_type(response).split(";")[1:]:
        name, _, value = part.strip().partition("=")
        if name.lower() == "charset":
            return value
    return ""


def _open_tag(element):
    """The start (or self-closing) tag of an HTML element node, or None."""
    return next((child for child in element.children if child.type in ("start_tag", "self_closing_tag")), None)


def _element_tag(element, source):
    """The tag name of an HTML element, or None."""
    tag = _open_tag(element)
    return None if tag is None else next((node_text(c, source) for c in tag.children if c.type == "tag_name"), None)


def _element_attr(element, name, source):
    """The value of a named attribute on an HTML element, or None when absent."""
    tag = _open_tag(element)
    if tag is None:
        return None
    for attribute in tag.children:
        if attribute.type != "attribute":
            continue
        attr_name = next((node_text(c, source) for c in walk(attribute) if c.type == "attribute_name"), None)
        if attr_name == name:
            return next((node_text(c, source) for c in walk(attribute) if c.type == "attribute_value"), "")
    return None


def _parse_selector(selector):
    """A simple CSS selector split into its optional tag, optional #id, and .class list."""
    tag = re.match(r"[a-zA-Z][\w-]*", selector)
    ident = re.search(r"#([\w-]+)", selector)
    return (tag.group(0) if tag else None, ident.group(1) if ident else None, re.findall(r"\.([\w-]+)", selector))


def _selector_matches(element, selector, source):
    """True if an HTML element matches a simple selector — a tag, #id, .class, or a combination."""
    tag, wanted_id, wanted_classes = _parse_selector(selector)
    if tag is not None and _element_tag(element, source) != tag:
        return False
    if wanted_id is not None and _element_attr(element, "id", source) != wanted_id:
        return False
    classes = (_element_attr(element, "class", source) or "").split()
    return all(cls in classes for cls in wanted_classes)


def _html_has_selector(body, selector):
    """True if the HTML body contains an element matching the simple CSS selector (tag / #id / .class)."""
    root = parse_html(body).root_node
    return any(node.type == "element" and _selector_matches(node, selector, body) for node in walk(root))


def register_http_steps(registry):
    """Register the section 8.4 standard protocol-level steps into a registry and return it: the response
    assertions, the request builders, the when-senders, and the multi-request session steps. Each handler
    is a pure returns-new-context; the response and client are read from the injected context contract."""

    def status_is(context, status):
        assert context["response"]["status"] == status
        return context

    def status_in_class(context, klass):
        assert context["response"]["status"] // 100 == int(klass[0])
        return context

    def content_type_is(context, mime):
        assert _mime(context["response"]) == mime
        return context

    def charset_is(context, charset):
        assert _charset(context["response"]) == charset
        return context

    def header_equals(context, name, value):
        assert context["response"]["headers"].get(name.lower()) == value
        return context

    def no_header(context, name):
        assert name.lower() not in context["response"]["headers"]
        return context

    def body_bytes_equal(context, literal):
        assert context["response"]["body"] == literal.encode("utf-8")
        return context

    def body_json(context, schema):
        assert context["schemas"][schema](json.loads(context["response"]["body"]))
        return context

    def body_html(context, selector):
        assert _html_has_selector(context["response"]["body"], selector)
        return context

    def sets_cookie(context, name, value):
        assert context["response"]["cookies"][name]["value"] == value
        return context

    def cookie_attribute(context, name, attribute):
        assert attribute in context["response"]["cookies"][name]["attributes"]
        return context

    def cookie_max_age(context, name, age):
        assert context["response"]["cookies"][name]["attributes"].get("Max-Age") == age
        return context

    def location_is(context, url):
        assert context["response"]["headers"].get("location") == url
        return context

    def request_header(context, name, value):
        request = _request(context)
        return {**context, "request": {**request, "headers": {**request["headers"], name: value}}}

    def request_cookie(context, name, value):
        request = _request(context)
        return {**context, "request": {**request, "cookies": {**request["cookies"], name: value}}}

    def request_body(context, content):
        return {**context, "request": {**_request(context), "body": content.encode("utf-8")}}

    def request_content_type(context, mime):
        return {**context, "request": {**_request(context), "content_type": mime}}

    def send(context, method, path, body):
        request = {**_request(context), "body": body}
        response = context["client"](method, path, request)
        return {**context, "previous_response": context.get("response"), "response": response, "request": _EMPTY_REQUEST}

    def post(context, path, content):
        return send(context, "POST", path, content.encode("utf-8"))

    def get(context, path):
        return send(context, "GET", path, _request(context)["body"])

    def delete(context, path):
        return send(context, "DELETE", path, _request(context)["body"])

    def reuse_set_cookie(context):
        request = _request(context)
        sent = {name: cookie["value"] for name, cookie in context["response"]["cookies"].items()}
        return {**context, "request": {**request, "cookies": {**request["cookies"], **sent}}}

    def reuse_session(context):
        request = _request(context)
        value = context["response"]["cookies"][_SESSION]["value"]
        return {**context, "request": {**request, "cookies": {**request["cookies"], _SESSION: value}}}

    def share_session(context):
        assert context["response"]["cookies"][_SESSION]["value"] == context["previous_response"]["cookies"][_SESSION]["value"]
        return context

    registry = register_step(registry, "then", "the response status is {status:int}", status_is)
    registry = register_step(registry, "then", "the response status is in {klass}", status_in_class)
    registry = register_step(registry, "then", 'the response Content-Type is "{mime}"', content_type_is)
    registry = register_step(registry, "then", 'the response charset is "{charset}"', charset_is)
    registry = register_step(registry, "then", 'the response header "{name}" equals "{value}"', header_equals)
    registry = register_step(registry, "then", 'the response has no header "{name}"', no_header)
    registry = register_step(registry, "then", 'the response body bytes equal "{literal}"', body_bytes_equal)
    registry = register_step(registry, "then", "the response body is JSON conforming to {schema}", body_json)
    registry = register_step(registry, "then", 'the response body is HTML containing the selector "{selector}"', body_html)
    registry = register_step(registry, "then", 'the response sets cookie "{name}" with value "{value}"', sets_cookie)
    registry = register_step(registry, "then", 'the response cookie "{name}" has attribute "{attribute}"', cookie_attribute)
    registry = register_step(registry, "then", 'the response cookie "{name}" has Max-Age {age:int}', cookie_max_age)
    registry = register_step(registry, "then", 'the response location is "{url}"', location_is)
    registry = register_step(registry, "given", 'a request with header "{name}" = "{value}"', request_header)
    registry = register_step(registry, "given", 'a request with cookie "{name}" = "{value}"', request_cookie)
    registry = register_step(registry, "given", 'a request with body "{content}"', request_body)
    registry = register_step(registry, "given", 'a request with Content-Type "{mime}"', request_content_type)
    registry = register_step(registry, "when", 'a POST request is sent to "{path}" with body "{content}"', post)
    registry = register_step(registry, "when", 'a GET request is sent to "{path}"', get)
    registry = register_step(registry, "when", 'a DELETE request is sent to "{path}"', delete)
    registry = register_step(registry, "when", "the previous response's Set-Cookie is used as the next request's Cookie", reuse_set_cookie)
    registry = register_step(registry, "when", "the session from the previous response is reused", reuse_session)
    registry = register_step(registry, "then", "the response and the previous response share the same session cookie value", share_session)
    return registry
