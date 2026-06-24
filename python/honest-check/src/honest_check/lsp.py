"""Language Server Protocol server (section 2.2).

`honest-check --lsp` speaks JSON-RPC 2.0 over stdio. It publishes diagnostics live
as the developer edits and answers the section 2.2 "Complete" requests — hover,
go-to-definition, workspace symbols, and code actions. Full-text sync keeps an open-
document store current (uri -> text); the store is threaded through every handler as
a value (section 8.1.1 pattern), never module state, so a request that carries only
a position can still be answered against the document's current text.

Split: the method handlers are PURE — (store, msg_id, params) -> (store, outgoing
messages) — calling the pure `check_source` and parse helpers. The only I/O is the
read/write framing loop, which is the boundary. Method dispatch is a table, not a branch.

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
                    "workspaceSymbolProvider": True,
                    "codeActionProvider": True,
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


# The declaration constructors that workspace/symbol surfaces, mapped to their LSP SymbolKind
# (5 Class, 8 Field, 12 Function) — section 2.2.
_SYMBOL_KINDS = {"vocabulary": 5, "binding": 8, "chain": 12, "validate_all": 12}


def _document_symbols(text: str, uri: str) -> list:
    """The vocabulary, binding, and chain declarations in one document as LSP symbols (section 2.2):
    a top-level assignment whose value constructs one of them, named by the assignment target. Pure."""
    source = text.encode("utf-8")
    root = parse_python(source).root_node
    symbols = []
    for node in walk(root):
        if node.type != "assignment":
            continue
        right = node.child_by_field_name("right")
        if right.type != "call":
            continue
        function = right.child_by_field_name("function")
        if function.type != "identifier":
            continue
        kind = _SYMBOL_KINDS.get(node_text(function, source))
        if kind is None:
            continue
        target = node.child_by_field_name("left")
        symbols.append({
            "name": node_text(target, source),
            "kind": kind,
            "location": {
                "uri": uri,
                "range": {
                    "start": {"line": target.start_point[0], "character": target.start_point[1]},
                    "end": {"line": target.end_point[0], "character": target.end_point[1]},
                },
            },
        })
    return symbols


def _on_workspace_symbol(store, msg_id, params):
    query = params.get("query", "").lower()
    symbols = [
        symbol
        for uri, text in store.items()
        for symbol in _document_symbols(text, uri)
        if query in symbol["name"].lower()
    ]
    return store, [_response(msg_id, symbols)]


def _code_actions(text: str, uri: str, lsp_range: dict) -> list:
    """Quick-fix code actions for the diagnostics in an LSP range (section 2.2): a suppression
    directive for each diagnostic whose line falls in the range. The edit appends a
    `# honest: ignore HC-XXXX` comment to that line, the one fix every rule supports. Pure."""
    lines = text.split("\n")
    start_line = lsp_range.get("start", {}).get("line", 0)
    end_line = lsp_range.get("end", {}).get("line", start_line)
    actions = []
    for d in check_source(text, uri):
        diagnostic_line = d["line"] - 1  # honest-check is 1-based, LSP 0-based
        if start_line <= diagnostic_line <= end_line:
            end_char = len(lines[diagnostic_line])
            actions.append({
                "title": f"Suppress {d['rule']} with a directive",
                "kind": "quickfix",
                "edit": {"changes": {uri: [{
                    "range": {
                        "start": {"line": diagnostic_line, "character": end_char},
                        "end": {"line": diagnostic_line, "character": end_char},
                    },
                    "newText": f"  # honest: ignore {d['rule']}",
                }]}},
            })
    return actions


def _on_code_action(store, msg_id, params):
    doc = params.get("textDocument", {})
    uri = doc.get("uri", "")
    return store, [_response(msg_id, _code_actions(store.get(uri, ""), uri, params.get("range", {})))]


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
    "workspace/symbol": _on_workspace_symbol,
    "textDocument/codeAction": _on_code_action,
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
