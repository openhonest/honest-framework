"""A development-only plaintext username/password AuthProvider (section 5.3 category).

INSECURE BY DESIGN — for local development only, never a non-development environment. Passwords are
compared in plaintext, and a user whose stored password is empty accepts ANY password, so a login form
lets anyone in as that user. This is the convenience the No-auth provider (section 5.3) gives, one step
more realistic: real usernames, optional passwords. It is not a default — an application must register
it explicitly — because the framework ships no default provider (section 3.2): a weak default is a false
sense of security.

The token wire format is 'username:password' (colon-separated, HTTP-Basic style). The recognizer accepts
a non-empty username followed by a colon; resolve_actor looks the user up in a fixed dev table and
resolves the actor when the stored password is empty (any password) or matches it. Everything is a pure
value the factory builds; the user table is captured as data, so a built provider is deterministic and
honest against the token-class contract.
"""

from honest_type import err, fault, ok

# With no table supplied, a single 'dev' user with an empty password — log in as 'dev' with anything.
_DEFAULT_USERS = {"dev": ""}


def _dev_recognizer(token):
    """The dev token wire format (section 2.2): a non-empty username, a colon, then the password. Pure."""
    return isinstance(token, str) and ":" in token and token.partition(":")[0] != ""


def _dev_resolver(users):
    """Build the boundary resolver over a {username: password} table (section 2.3): the actor resolves
    when the user exists and the stored password is empty (any password accepted) or matches; otherwise
    an unauthenticated fault. Pure — the table is captured as data."""
    def resolve(token):
        username, _, password = token.partition(":")
        if username not in users:
            return err(fault("forged", "no such dev user", "unauthenticated"))
        if users[username] == "" or users[username] == password:
            return ok({"id": username})
        return err(fault("bad_password", "wrong password for the dev user", "unauthenticated"))

    return resolve


def _dev_token_generator(users):
    """Build the token-class generator (section 2.4): a valid token for the first user, a malformed one
    with no colon, a missing (None) credential, and unknown-user tokens for the revoked/expired/forged
    classes — all of which resolve to unauthenticated. Pure."""
    first = sorted(users)[0]
    tokens = {
        "valid": first + ":" + users[first],
        "malformed": "no-colon-here",
        "missing": None,
        "revoked": "revoked-user:x",
        "expired": "expired-user:x",
        "forged": "forged-user:x",
    }

    def generate(class_name, context):
        return tokens[class_name]

    return generate


def dev_auth_provider(users=None):
    """A dev-only plaintext user/password AuthProvider (section 5.3 category). `users` is a
    {username: password} table; an empty stored password accepts any password (dev convenience). With no
    table it is a single 'dev' user with an empty password. INSECURE — development only. Pure factory
    returning a conforming AuthProvider value that passes the authentication-honesty contract."""
    table = dict(users) if users else dict(_DEFAULT_USERS)
    return {
        "name": "dev-plaintext",
        "actor_recognizer": _dev_recognizer,
        "resolve_actor": _dev_resolver(table),
        "test_token_generator": _dev_token_generator(table),
        "fault_mapping": {},
    }
