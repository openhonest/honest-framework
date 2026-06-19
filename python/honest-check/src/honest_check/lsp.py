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


def _on_initialize(msg_id, params) -> list[dict]:
    return [
        _response(
            msg_id,
            {
                "capabilities": {"textDocumentSync": 1},  # 1 = full document sync
                "serverInfo": {"name": "honest-check", "version": "0.1"},
            },
        )
    ]


def _on_did_open(msg_id, params) -> list[dict]:
    doc = params.get("textDocument", {})
    return [_publish(doc.get("uri", ""), doc.get("text", ""))]


def _on_did_change(msg_id, params) -> list[dict]:
    uri = params.get("textDocument", {}).get("uri", "")
    changes = params.get("contentChanges", [])
    text = changes[-1].get("text", "") if changes else ""
    return [_publish(uri, text)]


def _on_did_close(msg_id, params) -> list[dict]:
    uri = params.get("textDocument", {}).get("uri", "")
    return [
        {
            "jsonrpc": "2.0",
            "method": "textDocument/publishDiagnostics",
            "params": {"uri": uri, "diagnostics": []},
        }
    ]


def _on_shutdown(msg_id, params) -> list[dict]:
    return [_response(msg_id, None)]


def _noop(msg_id, params) -> list[dict]:
    return []


_HANDLERS = {
    "initialize": _on_initialize,
    "initialized": _noop,
    "textDocument/didOpen": _on_did_open,
    "textDocument/didChange": _on_did_change,
    "textDocument/didSave": _noop,
    "textDocument/didClose": _on_did_close,
    "shutdown": _on_shutdown,
}


def dispatch(method: str, msg_id, params: dict) -> list[dict]:
    """Route a request/notification to its handler (table dispatch). Pure."""
    return _HANDLERS.get(method, _noop)(msg_id, params)


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
    while True:
        message = _read_message(source)
        if message is None:
            return 0
        if message.get("method", "") == "exit":
            return 0
        for outgoing in dispatch(message.get("method", ""), message.get("id"), message.get("params", {})):
            _write_message(sink, outgoing)
