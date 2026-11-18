"""The one dense canonical request event, colocating all request telemetry in a single record so an
operational question needs no join (honest-observe.hd request_canonical, section 4.6).

It folds the facts already gathered for the request into one Event keyed by request_id, the join key
with the browser events (section 8.5): the HTTP method, path and status; the caller and session from
the auth partition; the primary chain, its link count and the ordered link_sequence; the intake token
and rejection counts; the database query count and total duration; the outcome result with its fault
code and category; and the total duration. Pure: it reads no world and returns no fault, the boundary
that calls it having the facts in hand.
"""

from honest_observe.types import Event

# The canonical request event's type and aggregate identity: it is the hf.request.completed envelope,
# keyed under the request aggregate so every request's telemetry is one row joinable by request_id.
_EVENT_TYPE = "hf.request.completed"
_EVENT_VERSION = "1.0"
_AGGREGATE_TYPE = "request"


def request_canonical(request_id, http_method, http_path, http_status, caller_id, session_id, chain_name, link_count, link_sequence, token_count, rejection_count, query_count, query_duration_ns, result, fault_code, fault_category, duration_ns):
    """Assemble the one dense canonical request Event, keyed by request_id, carrying all request
    telemetry in one record so an operational question needs no join (section 4.6). The auth partition
    holds the caller and session; the payload colocates the HTTP, chain, intake, persistence and
    outcome facts. Pure: it folds facts in hand, reads no world and returns no fault."""
    envelope: Event = {
        "event_id": request_id,
        "event_type": _EVENT_TYPE,
        "event_version": _EVENT_VERSION,
        "timestamp": "",
        "sequence": 0,
        "aggregate_type": _AGGREGATE_TYPE,
        "aggregate_id": request_id,
        "payload": {
            "request_id": request_id,
            "http_method": http_method,
            "http_path": http_path,
            "http_status": http_status,
            "chain_name": chain_name,
            "link_count": link_count,
            "link_sequence": link_sequence,
            "token_count": token_count,
            "rejection_count": rejection_count,
            "query_count": query_count,
            "query_duration_ns": query_duration_ns,
            "result": result,
            "fault_code": fault_code,
            "fault_category": fault_category,
            "duration_ns": duration_ns,
        },
        "auth": {"caller_id": caller_id, "session_id": session_id},
        "meta": {},
    }
    return envelope
