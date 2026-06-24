"""OpenTelemetry export (section 7): the pure half of the exporter.

Section 7.1 frames the OTel exporter as a projection — it reads the event log and emits OTel signals.
The projection itself is pure: an hf.* event maps to one OTel signal kind (section 7.1) and a set of
semantic-convention attributes (sections 7.2, 7.3). Running that projection against a configured SDK
exporter — `install_otel_exporter`, the background export loop, the network — is the boundary's, reached
through the injected exporter exactly as emit reaches the log through the injected runtime. So observe
never imports the opentelemetry SDK; it produces the signal as data and the boundary ships it.

The attribute mapping is dict-lookup polymorphism: a table of per-event-type builders, never a
discriminant if/elif chain. An event with no builder contributes no hf.* attributes (its signal may
still have a kind, e.g. a persist query whose db.* attributes are added from the persist event by the
boundary). `service.version` is the one standard attribute sourced from the event itself — from
`meta.release` — so it attaches to whatever event carries it.
"""

# Section 7.1: hf.* event type to OTel signal kind. An event type absent here is not a framework signal.
_SIGNAL_KINDS = {
    "hf.chain.started": "span_start",
    "hf.chain.completed": "span_end",
    "hf.link.executed": "child_span",
    "hf.link.faulted": "span_event",
    "hf.persist.query": "child_span",
    "hf.classify.completed": "metric_counter",
    "hf.state.transitioned": "span_event",
}


def _chain_started_attrs(payload):
    return {"hf.chain.name": payload["chain_name"], "hf.chain.link_count": payload["link_count"]}


def _chain_completed_attrs(payload):
    attrs = {"hf.chain.name": payload["chain_name"], "hf.chain.link_count": payload["link_count"]}
    if "fault_code" in payload:
        attrs["hf.chain.fault_code"] = payload["fault_code"]
    return attrs


def _link_executed_attrs(payload):
    return {
        "hf.link.name": payload["link_name"],
        "hf.link.boundary": payload["boundary"],
        "hf.link.mutations": payload["mutations"],
        "hf.link.singletons": payload["singletons"],
        "hf.link.nondeterminism": payload["nondeterminism"],
        "hf.link.io_calls": payload["io_calls"],
    }


def _link_faulted_attrs(payload):
    return {"hf.link.name": payload["link_name"]}


def _classify_attrs(payload):
    return {"hf.vocabulary.name": payload["vocabulary_name"], "hf.classify.rejection_count": payload["rejection_count"]}


def _state_attrs(payload):
    return {"hf.state.machine": payload["machine_name"], "hf.state.from": payload["from_state"], "hf.state.event": payload["event"], "hf.state.to": payload["to_state"]}


# Section 7.3: per-event-type attribute builders. The dispatch table is the type system.
_ATTRIBUTE_BUILDERS = {
    "hf.chain.started": _chain_started_attrs,
    "hf.chain.completed": _chain_completed_attrs,
    "hf.link.executed": _link_executed_attrs,
    "hf.link.faulted": _link_faulted_attrs,
    "hf.classify.completed": _classify_attrs,
    "hf.state.transitioned": _state_attrs,
}


def otel_signal_kind(event_type: str):
    """The OTel signal kind for an hf.* event (section 7.1), or None when the event is not a framework
    signal. Pure dict lookup."""
    return _SIGNAL_KINDS.get(event_type)


def otel_attributes(event: dict) -> dict:
    """The OTel semantic-convention attributes for an event (sections 7.2, 7.3): the hf.* attributes its
    event type contributes, plus `service.version` from `meta.release` when present. An event with no
    attribute builder contributes no hf.* attributes. Pure."""
    builder = _ATTRIBUTE_BUILDERS.get(event["event_type"])
    attrs = builder(event["payload"]) if builder else {}
    meta = event.get("meta")
    if meta and "release" in meta:
        attrs["service.version"] = meta["release"]
    return attrs


def otel_signal(event: dict) -> dict:
    """The projection's output for one event (section 7.1): its event type, OTel signal kind, and
    attributes, as data the boundary's exporter ships to the OTel SDK. Pure."""
    return {"event_type": event["event_type"], "kind": otel_signal_kind(event["event_type"]), "attributes": otel_attributes(event)}
