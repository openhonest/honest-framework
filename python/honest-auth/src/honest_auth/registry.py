"""Provider registration (section 3): the registry is a value, never module state.

`empty_registry()` yields a registry with no provider; `register_auth_provider` returns a NEW registry
holding the validated provider, or a fault (`already_registered` / `invalid_provider`); `registered_provider`
reads the active provider, or `None` when none is registered. The honest-gherkin step-registry pattern:
registration carries no shared mutable state, so two startups never collide. Pure throughout.
"""

from honest_type import err, fault, ok

# The five fields every AuthProvider value must carry (section 2).
_REQUIRED_FIELDS = ("name", "actor_recognizer", "resolve_actor", "test_token_generator", "fault_mapping")


def empty_registry():
    """A registry with no provider registered (section 3)."""
    return {"provider": None}


def validate_provider(provider):
    """Check a provider value carries all five required fields (section 2). ok(provider) or
    err(invalid_provider) listing the missing fields. Pure."""
    missing = [name for name in _REQUIRED_FIELDS if name not in provider]
    if missing:
        return err(fault("invalid_provider", f"AuthProvider is missing required fields: {missing}", "client", detail=missing))
    return ok(provider)


def register_auth_provider(registry, provider):
    """Register the single active provider (section 3): a NEW registry holding it. Returns
    err(already_registered) if one is already registered, err(invalid_provider) if the provider is
    malformed, else ok(new_registry). Never mutates its argument. Pure."""
    if registry["provider"] is not None:
        return err(fault("already_registered", "an AuthProvider is already registered for this application", "client"))
    validated = validate_provider(provider)
    if "err" in validated:
        return validated
    return ok({"provider": provider})


def registered_provider(registry):
    """The active provider, or None when none is registered (section 3.1). Pure."""
    return registry["provider"]
