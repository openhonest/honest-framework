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


def link_summary(link_name: str, duration_ns: int, result: str, fault_code=None) -> dict:
    """One link's entry in a canonical request event's link_sequence (section 4.6); the fault code
    appears only on error. Pure."""
    summary = {"link_name": link_name, "duration_ns": duration_ns, "result": result}
    if fault_code is not None:
        summary["fault_code"] = fault_code
    return summary


def request_canonical(request_id: str, http_method: str, http_path: str, http_status: int, link_count: int, link_sequence: list, token_count: int, rejection_count: int, query_count: int, query_duration_ns: int, result: str, duration_ns: int, caller_id=None, session_id=None, chain_name=None, fault_code=None, fault_category=None) -> dict:
    """The hf.request.canonical event (section 4.6): every meaningful fact about a request in one
    record, so an operational question needs no join. Optional identity, chain, and fault fields
    appear only when supplied. Pure — the boundary assembles the arguments from the request's events."""
    payload = {
        "http_method": http_method,
        "http_path": http_path,
        "http_status": http_status,
        "link_count": link_count,
        "link_sequence": list(link_sequence),
        "token_count": token_count,
        "rejection_count": rejection_count,
        "query_count": query_count,
        "query_duration_ns": query_duration_ns,
        "result": result,
        "duration_ns": duration_ns,
        "request_id": request_id,
        "source": "server",
    }
    for key, value in (("caller_id", caller_id), ("session_id", session_id), ("chain_name", chain_name), ("fault_code", fault_code), ("fault_category", fault_category)):
        if value is not None:
            payload[key] = value
    return {"event_type": "hf.request.canonical", "aggregate_type": "request", "aggregate_id": request_id, "payload": payload}


def app_started(app_name: str, environment: str, chains_loaded: int, links_loaded: int, vocabs_loaded: int, release=None) -> dict:
    """The hf.app.started event (section 4.7); the release appears when supplied. Pure."""
    payload = {
        "app_name": app_name,
        "environment": environment,
        "chains_loaded": chains_loaded,
        "links_loaded": links_loaded,
        "vocabs_loaded": vocabs_loaded,
    }
    if release is not None:
        payload["release"] = release
    return {"event_type": "hf.app.started", "aggregate_type": "app", "aggregate_id": app_name, "payload": payload}


def app_stopped(app_name: str, uptime_ns: int, reason: str) -> dict:
    """The hf.app.stopped event (section 4.7): how long the app ran and why it stopped. Pure."""
    return {
        "event_type": "hf.app.stopped",
        "aggregate_type": "app",
        "aggregate_id": app_name,
        "payload": {"app_name": app_name, "uptime_ns": uptime_ns, "reason": reason},
    }


def app_error(app_name: str, error_type: str, message: str, traceback=None, context=None) -> dict:
    """The hf.app.error event (section 4.7): an exception escaping the boundary or occurring outside a
    chain. The traceback and context appear when supplied (traceback in development only). Pure."""
    payload = {"error_type": error_type, "message": message}
    if traceback is not None:
        payload["traceback"] = traceback
    if context is not None:
        payload["context"] = context
    return {"event_type": "hf.app.error", "aggregate_type": "app", "aggregate_id": app_name, "payload": payload}
