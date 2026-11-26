# scenario: execute_chain_async runs links in sequence, awaiting any async link
# inherits: hd=python/honest-type/honest-type.hd::execute_chain_async -> feature=specs/features/honest-type.feature::execute_chain_async runs links in sequence, awaiting any async link
import asyncio
from copy import deepcopy

_INITIAL = {"slots": {"request": "example"}}
_FAULT = {
    "is_err": True,
    "code": "invalid_request",
    "message": "The request could not be accepted",
    "category": "client",
    "results": [],
    "detail": {"request": "example"},
}


def probe_execute_chain_async_first_fault():
    from honest_type.chains import execute_chain_async

    ran = []
    first_fault = deepcopy(_FAULT)

    async def reject(manifest):
        ran.append(("reject", manifest))
        return first_fault

    async def complete(manifest):
        ran.append(("complete", manifest))
        return manifest

    async def publish(manifest):
        ran.append(("publish", manifest))
        return manifest

    initial = deepcopy(_INITIAL)
    actual = asyncio.run(execute_chain_async([reject, complete, publish], initial))
    expected_calls = [("reject", _INITIAL)]
    failures = []
    if actual != _FAULT:
        failures.append(f"Expected the original fault {_FAULT!r}, received {actual!r}")
    if ran != expected_calls:
        failures.append(f"Expected only the first link {expected_calls!r}, observed {ran!r}")
    return failures
