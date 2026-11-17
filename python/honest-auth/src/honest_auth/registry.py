"""Registration and the value registry (honest-auth-architecture.md §3). The registry is a value a
run threads, not module state: empty_registry seeds it, register_auth_provider returns a new one
carrying the provider, and registered_provider reads the active provider back. validate_provider
checks a provider is well-formed before it is admitted. Pure throughout: no world, no mutation of an
argument — two runs never collide (the honest-gherkin step-registry pattern).

The single-use helpers each declared function needs nest inside it, so the module's column-0
functions are exactly the four the .hd declares.
"""

from honest_type import is_fault

from honest_auth._util import _pick
from honest_auth.types import (
    NOTHING,
    REQUIRED_CATEGORIES,
    REQUIRED_FIELDS,
    auth_fault,
)


def empty_registry():
    """Return a fresh Registry with no provider — its provider field is NOTHING (§3). The seed
    register_auth_provider extends. Pure: it takes nothing and reads no world."""
    return {"provider": NOTHING}


def registered_provider(registry):
    """Return the registry's active provider, or NOTHING when none is registered (§3, §3.2). Having
    no provider is a valid bounded absence, not a failure, so the empty case is NOTHING: it carries no
    is_err tag and is never recognized by is_fault. Pure: a field read, no world, no fault."""
    return registry["provider"]


def validate_provider(provider):
    """Check a provider is well-formed before it is registered (§3, §9.1). It confirms the provider
    supplies all five AuthProvider fields and that fault_mapping retains the unauthenticated category
    required of every mapping (§2.5). It returns the provider unchanged when well-formed, or an
    auth_fault with code invalid_provider whose detail names the malformed fields (§3). Pure: it
    builds no registry, performs no I/O and reads no world."""

    def _mapping_dropped():
        # The required fault categories the provider's fault_mapping drops (§2.5). Read only when
        # fault_mapping is present — an absent mapping is already a missing field, so the absent case
        # returns an empty list rather than defaulting the read, which would file a missing mapping
        # under a present one (P16).
        return _pick(
            "fault_mapping" in provider,
            lambda: list(filter(lambda category: category not in provider["fault_mapping"], REQUIRED_CATEGORIES)),
            lambda: [],
        )

    missing = list(filter(lambda field: field not in provider, REQUIRED_FIELDS))
    problems = missing + _mapping_dropped()
    return _pick(
        not problems,
        lambda: provider,
        lambda: auth_fault(
            "conflict",
            "invalid_provider",
            f"provider is malformed; fix these fields: {problems}",
            {"malformed_fields": problems},
        ),
    )


def register_auth_provider(registry, provider):
    """Register the single active provider, returning a new Registry carrying it on success or an
    auth_fault on failure, recognized by is_fault — no envelope (§3). It faults already_registered
    when the registry already holds a provider, since exactly one provider is active per application,
    and invalid_provider — via validate_provider — when the provider is malformed. It never mutates
    its argument. Pure: it reads no world; registration happens at application startup."""

    def _register_validated():
        # Admit a provider into a fresh registry once the registry is known empty: validate it, and
        # return the validation fault unchanged if malformed, or a new Registry carrying it if
        # well-formed (§3). The new dict is why registration never mutates its argument.
        validated = validate_provider(provider)
        return _pick(
            is_fault(validated),
            lambda: validated,
            lambda: {"provider": provider},
        )

    return _pick(
        registered_provider(registry) is NOTHING,
        _register_validated,
        lambda: auth_fault(
            "conflict",
            "already_registered",
            "a provider is already active; exactly one provider is active per application",
            {"existing": registered_provider(registry)["name"]},
        ),
    )
