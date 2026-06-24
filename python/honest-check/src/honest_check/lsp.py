"""Language Server Protocol server (section 2.2).

`honest-check --lsp` speaks JSON-RPC 2.0 over stdio and publishes honest-check
diagnostics live as the developer edits: open/change a document, get inline
violations. Full-text sync, so each change carries the whole document and the
handlers need no document state.

Split: the method handlers are PURE (a message in, a list of outgoing messages out;
they call the pure `check_source`). The only I/O is the read/write framing loop,
which is the boundary. Method dispatch is a table, not a branch.

# honest: disable HC-P004
"""

import json
import sys

from honest_parse import node_text, parse_python, walk

from honest_check.diagnostics import Diagnostic
from honest_check.rules import check_source

# honest-check severity -> LSP DiagnosticSeverity (1 error, 2 warning, 3 information).
_LSP_SEVERITY = {"error": 1, "warning": 2, "info": 3}


def to_lsp_diagnostic(d: Diagnostic) -> dict:
    """Convert a honest-check Diagnostic (1-based) to an LSP Diagnostic (0-based)."""
    line = max(d["line"] - 1, 0)
    col = max(d["col"] - 1, 0)
    return {
        "range": {
            "start": {"line": line, "character": col},
            "end": {"line": line, "character": col + 1},
        },
        "severity": _LSP_SEVERITY.get(d["severity"], 3),
        "code": d["rule"],
        "source": "honest-check",
        "message": d["message"],
    }


def _publish(uri: str, text: str) -> dict:
    """A textDocument/publishDiagnostics notification for a document's current text."""
    diagnostics = [to_lsp_diagnostic(d) for d in check_source(text, uri)]
    return {
        "jsonrpc": "2.0",
        "method": "textDocument/publishDiagnostics",
        "params": {"uri": uri, "diagnostics": diagnostics},
    }


def _response(msg_id, result) -> dict:
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


# The open documents, mapped uri -> current text. Threaded through every handler as a value (section
# 8.1.1 pattern), never hidden state: full-text sync keeps each entry current, and the request
# handlers (hover and friends) read it to answer questions about a position the request does not carry.
def _on_initialize(store, msg_id, params):
    return store, [
        _response(
            msg_id,
            {
                "capabilities": {
                    "textDocumentSync": 1,  # 1 = full document sync
                    "hoverProvider": True,
                    "definitionProvider": True,
                },
                "serverInfo": {"name": "honest-check", "version": "0.1"},
            },
        )
    ]


def _on_did_open(store, msg_id, params):
    doc = params.get("textDocument", {})
    uri, text = doc.get("uri", ""), doc.get("text", "")
    return {**store, uri: text}, [_publish(uri, text)]


def _on_did_change(store, msg_id, params):
    uri = params.get("textDocument", {}).get("uri", "")
    changes = params.get("contentChanges", [])
    text = changes[-1].get("text", "") if changes else ""
    return {**store, uri: text}, [_publish(uri, text)]


def _on_did_close(store, msg_id, params):
    uri = params.get("textDocument", {}).get("uri", "")
    kept = {key: value for key, value in store.items() if key != uri}
    return kept, [
        {
            "jsonrpc": "2.0",
            "method": "textDocument/publishDiagnostics",
            "params": {"uri": uri, "diagnostics": []},
        }
    ]


def _hover_contents(text: str, uri: str, position: dict):
    """The hover documentation at an LSP position (section 2.2): the rule and message of a diagnostic
    on that line, or None when nothing is flagged there. The diagnostic message is the rule's
    documentation. Pure."""
    line = position.get("line", 0) + 1  # LSP is 0-based, honest-check diagnostics 1-based
    for d in check_source(text, uri):
        if d["line"] == line:
            return {"kind": "markdown", "value": f"**{d['rule']}**: {d['message']}"}
    return None


def _on_hover(store, msg_id, params):
    doc = params.get("textDocument", {})
    uri = doc.get("uri", "")
    contents = _hover_contents(store.get(uri, ""), uri, params.get("position", {}))
    return store, [_response(msg_id, {"contents": contents} if contents is not None else None)]


def _node_at(root, line: int, col: int):
    """The identifier node whose span covers the 0-based (line, col), or None (section 2.2). Pure."""
    for node in walk(root):
        if node.type != "identifier":
            continue
        if node.start_point <= (line, col) < node.end_point:
            return node
    return None


def _definition_of(root, source: bytes, name: str):
    """The node where `name` is defined in the document — an assignment target or a function
    definition name (section 2.2) — or None. Pure."""
    for node in walk(root):
        if node.type == "assignment" and node_text(node.child_by_field_name("left"), source) == name:
            return node.child_by_field_name("left")
        if node.type == "function_definition" and node_text(node.child_by_field_name("name"), source) == name:
            return node.child_by_field_name("name")
    return None


def _definition_location(text: str, uri: str, position: dict):
    """The go-to-definition location for the identifier at an LSP position (section 2.2): where it is
    defined in the same document, or None when the position is not an identifier or has no definition.
    Pure."""
    source = text.encode("utf-8")
    root = parse_python(source).root_node
    identifier = _node_at(root, position.get("line", 0), position.get("character", 0))
    if identifier is None:
        return None
    target = _definition_of(root, source, node_text(identifier, source))
    if target is None:
        return None
    return {
        "uri": uri,
        "range": {
            "start": {"line": target.start_point[0], "character": target.start_point[1]},
            "end": {"line": target.end_point[0], "character": target.end_point[1]},
        },
    }


def _on_definition(store, msg_id, params):
    doc = params.get("textDocument", {})
    uri = doc.get("uri", "")
    return store, [_response(msg_id, _definition_location(store.get(uri, ""), uri, params.get("position", {})))]


def _on_shutdown(store, msg_id, params):
    return store, [_response(msg_id, None)]


def _noop(store, msg_id, params):
    return store, []


_HANDLERS = {
    "initialize": _on_initialize,
    "initialized": _noop,
    "textDocument/didOpen": _on_did_open,
    "textDocument/didChange": _on_did_change,
    "textDocument/didSave": _noop,
    "textDocument/didClose": _on_did_close,
    "textDocument/hover": _on_hover,
    "textDocument/definition": _on_definition,
    "shutdown": _on_shutdown,
}


def dispatch(store: dict, method: str, msg_id, params: dict):
    """Route a request/notification to its handler (table dispatch); returns (store, outgoing). The
    document store is threaded in and back out, never held as module state. Pure."""
    return _HANDLERS.get(method, _noop)(store, msg_id, params)


def _read_message(stream):
    """Read one LSP-framed JSON-RPC message from a binary stream, or None at EOF."""
    content_length = 0
    while True:
        line = stream.readline()
        if not line:
            return None
        header = line.strip()
        if header == b"":
            break
        if header.lower().startswith(b"content-length:"):
            content_length = int(header.split(b":", 1)[1].strip())
    body = stream.read(content_length)
    if not body:
        return None
    return json.loads(body.decode("utf-8"))


def _write_message(stream, message: dict) -> None:
    """Write one LSP-framed JSON-RPC message to a binary stream."""
    data = json.dumps(message).encode("utf-8")
    stream.write(f"Content-Length: {len(data)}\r\n\r\n".encode("ascii") + data)
    stream.flush()


def serve(stdin=None, stdout=None) -> int:
    """Run the stdio JSON-RPC loop until `exit` or EOF. The boundary."""
    source = sys.stdin.buffer if stdin is None else stdin
    sink = sys.stdout.buffer if stdout is None else stdout
    store: dict = {}
    while True:
        message = _read_message(source)
        if message is None:
            return 0
        if message.get("method", "") == "exit":
            return 0
        store, outgoing = dispatch(store, message.get("method", ""), message.get("id"), message.get("params", {}))
        for response in outgoing:
            _write_message(sink, response)
