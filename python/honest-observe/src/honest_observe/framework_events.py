"""The framework event catalogue (section 4): pure builders for the fixed set of `hf.*` events the
framework emits automatically.

Each builder returns the four things `emit` needs — event_type, aggregate_type, aggregate_id, and a
payload — for one framework event, so a boundary instruments a chain, link, classification, or
state-machine transition by calling the builder and threading the result into `emit`. The builders
are pure data construction: no I/O, no clock, no imports of the modules they describe. They are the
schema of section 4 made executable, so honest-test enumerates them and a projection can rely on the
exact field shape. The honest-persist events (section 4.5) and proof events (section 4.8) are built
in their own modules; this catalogue covers the chain, link, classification, state-machine,
canonical-request, and application-lifecycle events.

Optional payload fields — a fault on a successful-shaped event, an input manifest — appear only when
supplied, so a reader never has to distinguish absent from null.
"""


def chain_started(chain_name: str, link_count: int, input_types: list) -> dict:
    """The hf.chain.started event (section 4.1). Pure."""
    return {
        "event_type": "hf.chain.started",
        "aggregate_type": "chain",
        "aggregate_id": chain_name,
        "payload": {"chain_name": chain_name, "link_count": link_count, "input_types": list(input_types)},
    }


def chain_completed(chain_name: str, link_count: int, duration_ns: int, result: str, fault_code=None, fault_category=None) -> dict:
    """The hf.chain.completed event (section 4.1); the fault code and category appear when the chain
    finished in error. Pure."""
    payload = {"chain_name": chain_name, "duration_ns": duration_ns, "link_count": link_count, "result": result}
    if fault_code is not None:
        payload["fault_code"] = fault_code
    if fault_category is not None:
        payload["fault_category"] = fault_category
    return {"event_type": "hf.chain.completed", "aggregate_type": "chain", "aggregate_id": chain_name, "payload": payload}


def link_executed(link_name: str, chain_name: str, duration_ns: int, result: str, boundary: bool, mutations: int, singletons: int, nondeterminism: bool, io_calls: int, fault_code=None) -> dict:
    """The hf.link.executed event (section 4.2), carrying the honest-framework honesty measurements —
    mutations, singleton accesses, nondeterminism, and I/O calls — alongside the result. The fault
    code appears when the link returned an error. Pure."""
    payload = {
        "link_name": link_name,
        "chain_name": chain_name,
        "duration_ns": duration_ns,
        "result": result,
        "boundary": boundary,
        "mutations": mutations,
        "singletons": singletons,
        "nondeterminism": nondeterminism,
        "io_calls": io_calls,
    }
    if fault_code is not None:
        payload["fault_code"] = fault_code
    return {"event_type": "hf.link.executed", "aggregate_type": "link", "aggregate_id": link_name, "payload": payload}


def link_faulted(link_name: str, chain_name: str, fault_code: str, fault_category: str, fault_message: str, input_manifest=None) -> dict:
    """The hf.link.faulted event (section 4.2); the input manifest is included at error severity only,
    when supplied. Pure."""
    payload = {
        "link_name": link_name,
        "chain_name": chain_name,
        "fault_code": fault_code,
        "fault_category": fault_category,
        "fault_message": fault_message,
    }
    if input_manifest is not None:
        payload["input_manifest"] = input_manifest
    return {"event_type": "hf.link.faulted", "aggregate_type": "link", "aggregate_id": link_name, "payload": payload}


def classify_completed(vocabulary_name: str, token_count: int, rejection_count: int, duration_ns: int, rejection_reasons: dict) -> dict:
    """The hf.classify.completed event (section 4.3): how many tokens were classified and rejected,
    and the reason histogram. Pure."""
    return {
        "event_type": "hf.classify.completed",
        "aggregate_type": "classify",
        "aggregate_id": vocabulary_name,
        "payload": {
            "vocabulary_name": vocabulary_name,
            "token_count": token_count,
            "rejection_count": rejection_count,
            "duration_ns": duration_ns,
            "rejection_reasons": dict(rejection_reasons),
        },
    }


def state_transitioned(machine_name: str, entity_id: str, from_state: str, event: str, to_state: str, duration_ns: int) -> dict:
    """The hf.state.transitioned event (section 4.4); the aggregate is machine_name:entity_id. Pure."""
    return {
        "event_type": "hf.state.transitioned",
        "aggregate_type": "state_machine",
        "aggregate_id": machine_name + ":" + entity_id,
        "payload": {
            "machine_name": machine_name,
            "entity_id": entity_id,
            "from_state": from_state,
            "event": event,
            "to_state": to_state,
            "duration_ns": duration_ns,
        },
    }


def state_rejected(machine_name: str, entity_id: str, current_state: str, event: str, fault_code: str) -> dict:
    """The hf.state.rejected event (section 4.4): a transition that did not fire, with its fault code.
    Pure."""
    return {
        "event_type": "hf.state.rejected",
        "aggregate_type": "state_machine",
        "aggregate_id": machine_name + ":" + entity_id,
        "payload": {
            "machine_name": machine_name,
            "entity_id": entity_id,
            "current_state": current_state,
            "event": event,
            "fault_code": fault_code,
        },
    }
