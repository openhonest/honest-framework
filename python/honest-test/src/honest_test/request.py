"""The §8.4 request-construction and send functions (spec section 8.4).

Four Given builders accumulate a neutral Request one field at a time; two When transforms carry a
previous Response's cookies into the next Request; and send_request passes the accumulated Request
through the injected client — the one seam that touches the world — and returns the neutral Response
the client filled. Every builder and transform returns a new Request and mutates nothing it was
handed; send_request does no I/O of its own, exactly as evaluate_case (section 8.6) only drives the
functions injected through its map. All pure but for the one injected client.
"""


def with_header(request: dict, name: str, value: str) -> dict:
    """Add a header to a request under construction (spec section 8.4), the builder behind
    `Given a request with header "{name}" = "{value}"`. Returns a new Request whose headers carry
    name -> value, every other field carried unchanged, leaving the request handed in untouched."""
    headers = {**request["headers"], name: value}
    return {**request, "headers": headers}


def with_cookie(request: dict, name: str, value: str) -> dict:
    """Add a cookie to a request under construction (spec section 8.4), the builder behind
    `Given a request with cookie "{name}" = "{value}"`. Returns a new Request whose cookies carry
    name -> value, every other field carried unchanged, leaving the request handed in untouched."""
    cookies = {**request["cookies"], name: value}
    return {**request, "cookies": cookies}


def with_body(request: dict, content: str) -> dict:
    """Set the body of a request under construction (spec section 8.4), the builder behind
    `Given a request with body "{content}"`. Returns a new Request whose body is content, every
    other field carried unchanged, leaving the request handed in untouched."""
    return {**request, "body": content}


def with_content_type(request: dict, mime_type: str) -> dict:
    """Set the Content-Type of a request under construction (spec section 8.4), the builder behind
    `Given a request with Content-Type "{mime_type}"`. Returns a new Request whose content_type is
    mime_type, every other field carried unchanged, leaving the request handed in untouched."""
    return {**request, "content_type": mime_type}


def carry_cookie(previous: dict, request: dict) -> dict:
    """Carry the previous response's Set-Cookie into the next request's Cookie (spec section 8.4),
    the transform behind `When the previous response's Set-Cookie is used as the next request's
    Cookie`. Reads every Cookie off previous and returns a new Request carrying each one's
    name -> value into its cookies, every other field carried unchanged, both inputs untouched."""
    carried = {cookie["name"]: cookie["value"] for cookie in previous["cookies"]}
    cookies = {**request["cookies"], **carried}
    return {**request, "cookies": cookies}


def reuse_session(previous: dict, request: dict) -> dict:
    """Reuse only the session cookie from the previous response in the next request (spec section
    8.4), the transform behind `When the session from the previous response is reused`. Reads only
    the cookie named "session" off previous and returns a new Request carrying session -> value into
    its cookies, every other previous cookie and every other field left out, both inputs untouched."""
    session = {"session": cookie["value"] for cookie in previous["cookies"] if cookie["name"] == "session"}
    cookies = {**request["cookies"], **session}
    return {**request, "cookies": cookies}


def send_request(client, method: str, path: str, request: dict) -> dict:
    """Send the accumulated request through the injected client and return the neutral Response the
    client filled (spec section 8.4), the pass-through behind the When send steps. client is the
    injected boundary bound to the running app, called exactly once with the method, path and
    request; it sends the real request and returns honest-test's neutral Response already filled.
    send_request does no I/O of its own — the client is the seam — so it is edge, not a boundary."""
    return client(method, path, request)
