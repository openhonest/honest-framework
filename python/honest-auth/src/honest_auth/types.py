"""The honest-auth data shapes (section 2): the AuthProvider contract and the registry, as data.

These are TypedDicts — the contract is data, not behaviour. A provider is a plain value with five
fields; the registry is a value holding at most one provider. The framework defines the interface;
implementations are plugins that supply a value of this shape.
"""

from typing import Callable, TypedDict


class AuthProvider(TypedDict):
    """An authentication plugin (section 2): validate a credential at the boundary, resolve the actor."""

    name: str
    actor_recognizer: Callable  # (token) -> bool: the token wire-format recognizer
    resolve_actor: Callable  # (token) -> Result[Actor, Fault]: validate + identify, at the boundary
    test_token_generator: Callable  # (class_name) -> token: produces token classes for tests
    fault_mapping: dict  # {category: http_status}


class Registry(TypedDict):
    """The single active provider per application, held as a value (section 3), never module state."""

    provider: AuthProvider | None
