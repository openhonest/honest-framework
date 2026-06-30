"""honest-auth: the authentication interface layer (section 1).

The framework does not implement authentication; it defines the `AuthProvider` contract and the boundary
flow. Identity is validated at the boundary and passed inward as data; the pure interior never re-derives
it. The registry is a value (section 3); the provider's recognizer and resolver are the injected boundary
I/O. Everything honest-auth itself ships is pure.
"""

from honest_auth.authenticate import authenticate, fault_status
from honest_auth.registry import (
    empty_registry,
    register_auth_provider,
    registered_provider,
    validate_provider,
)
from honest_auth.types import AuthProvider, Registry

__all__ = [
    "AuthProvider",
    "Registry",
    "empty_registry",
    "register_auth_provider",
    "registered_provider",
    "validate_provider",
    "authenticate",
    "fault_status",
]
