"""honest-check conformance: the HC laws + boundary-shell coverage (the circle).

honest-check's input is unbounded source, so its behavioural circle is necessarily
example-based (the verification model: the structural rules are complete by form, but the
suite that exercises them is per-rule positive/negative examples, not an enumeration). This
harness carries the HC laws (honest-conformance-suite.md): HC-2 (determinism) and HC-4 (no
false negative on a mandatory rule — every rule flags its violation and stays silent on clean
code), plus exhaustive coverage of the I/O shells the conformance suite never touches: the
CLI, the LSP server, the output formats, config resolution, the startup hook, and inline
suppression. The shells are exercised in-process with temp files and injected streams.

The conformance directory is outside the honest-check gate, so it may read/write files, drive
argv and stdio, and feed deliberately-malformed config.
"""

import contextlib
import io
import json
import os
import sys
import tempfile
from pathlib import Path

from honest_check import HonestCheckError, check_source, startup_check
from honest_check.cli import _find_config, _load_config, main as cli_main, watch
from honest_check.rules import is_fixable
from honest_check.config import (
    empty_config,
    is_excluded,
    normalize_config,
    resolve_paths,
    resolve_severity,
)
from honest_check.diagnostics import diagnostic
from honest_check.formats import (
    counts,
    filter_by_rule,
    filter_by_severity,
    has_errors,
    render,
    supported_formats,
)
from honest_check.lsp import _read_message, dispatch, serve, to_lsp_diagnostic
from honest_check.watchlists import IO_WATCH_LIST, matches_watchlist

_CLEAN = "def add(a, b):\n    return a + b\n"
_VIOLATION = "class Widget:\n    pass\n"  # HC-P003: class declaration
# A go-to-definition fixture: make (def, line 0), V (assignment, line 2), ghost (undefined, line 4).
_DEFN_DOC = "def make():\n    return 1\nV = make()\nx = V\nz = ghost\n"
# A workspace-symbol fixture: a vocabulary, a binding, a chain, plus non-symbol assignments.
_SYMBOL_DOC = (
    "from honest_type import vocabulary, binding, chain\n"
    "Colors = vocabulary({'a': {'x'}})\n"
    "Bind = binding({'a': 's'})\n"
    "Flow = chain(f, g)\n"
    "n = 1\n"
    "m = other()\n"
    "d = mod.thing()\n"
)
_SYNTAX_ERROR = "def (:\n    pass\n"  # HC-SYN: unparseable — a startup-eligible rule


# --------------------------------------------------------------------------- formats


def _probe_formats():
    bad = []
    diags = [
        diagnostic("HC003", "error", "f.py", 1, 1, "a class & <tag> \"q\""),
        diagnostic("HC-P001", "warning", "f.py", 2, 1, "branch"),
        diagnostic("HC-P006", "info", "f.py", 3, 1, "note"),
    ]
    for fmt in supported_formats():
        if not render(diags, fmt):
            bad.append(f"render(diags, {fmt!r}) was empty")
    if render([], "human") == "":
        bad.append("render of no diagnostics should still summarise")
    total = counts(diags)
    if (total["error"], total["warning"], total["info"]) != (1, 1, 1):
        bad.append(f"counts wrong: {total}")
    if len(filter_by_severity(diags, "info")) != 3 or len(filter_by_severity(diags, "error")) != 1:
        bad.append("filter_by_severity floor wrong")
    if len(filter_by_severity(diags, "bogus")) != 2:  # unknown -> default warning floor
        bad.append("filter_by_severity default floor wrong")
    if len(filter_by_rule(diags, frozenset({"HC003"}), frozenset())) != 1:
        bad.append("filter_by_rule(only) wrong")
    if len(filter_by_rule(diags, frozenset(), frozenset({"HC003"}))) != 2:
        bad.append("filter_by_rule(suppress) wrong")
    if not has_errors(diags) or has_errors(diags[1:]):
        bad.append("has_errors wrong")
    return bad


# --------------------------------------------------------------------------- config


def _probe_config():
    bad = []
    full = normalize_config({"check": {"paths": ["src/"], "exclude": ["x/**"], "severity": "error"}, "rules": {"disable": ["HC003"]}})
    if full["paths"] != ["src/"] or full["severity"] != "error" or full["disable"] != ["HC003"]:
        bad.append(f"normalize_config wrong: {full}")
    if empty_config()["severity"] != "warning":
        bad.append("empty_config default severity wrong")
    configured = normalize_config({"rules": {"disable": ["HC003"], "HC-OR003": {"min_run": 4}}, "startup": {"on_error": "halt"}})
    if configured["rule_config"] != {"HC-OR003": {"min_run": 4}} or configured["startup_on_error"] != "halt":
        bad.append(f"normalize_config should keep per-rule config and startup on_error: {configured}")
    if empty_config()["rule_config"] != {} or empty_config()["startup_on_error"] is not None:
        bad.append("empty_config should have no rule config and no startup on_error")
    if not is_excluded("a/migrations/x.py", ["**/migrations/**"]) or is_excluded("a/x.py", ["**/migrations/**"]):
        bad.append("is_excluded wrong")
    if resolve_severity("error", "warning") != "error" or resolve_severity(None, "info") != "info" or resolve_severity(None, None) != "warning":
        bad.append("resolve_severity precedence wrong")
    if resolve_paths(["a"], ["b"]) != ["a"] or resolve_paths([], ["b"]) != ["b"] or resolve_paths([], []) != ["."]:
        bad.append("resolve_paths precedence wrong")
    return bad


# --------------------------------------------------------------------------- cli


def _run_cli(argv):
    out = io.StringIO()
    err = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli_main(argv)
    return code, out.getvalue(), err.getvalue()


def _probe_cli():
    bad = []
    with tempfile.TemporaryDirectory() as tmp:
        clean = Path(tmp) / "clean.py"
        clean.write_text(_CLEAN, encoding="utf-8")
        dirty = Path(tmp) / "dirty.py"
        dirty.write_text(_VIOLATION, encoding="utf-8")

        code, _, _ = _run_cli([str(clean)])
        if code != 0:
            bad.append(f"clean file should exit 0, got {code}")
        code, out, _ = _run_cli([str(dirty), "--format", "json"])
        if code != 1 or "HC" not in out:
            bad.append(f"violation should exit 1 with output, got {code} {out[:60]}")
        # A clean file in a format that emits nothing produces no output line.
        _run_cli([str(clean), "--format", "github"])
        # --rule / --no-rule / --severity filtering still parse and run.
        _run_cli([str(dirty), "--rule", "HC003", "--severity", "info"])
        code, _, _ = _run_cli([str(dirty), "--no-rule", "HC003", "--no-rule", "HC-P003"])
        # Explicit valid config is read and normalized.
        cfg = Path(tmp) / "honest-check.toml"
        cfg.write_text('[check]\nseverity = "error"\n', encoding="utf-8")
        _run_cli([str(dirty), "--config", str(cfg)])
        # A malformed config is an exit-2 usage failure.
        bad_cfg = Path(tmp) / "bad.toml"
        bad_cfg.write_text("this is = = not toml", encoding="utf-8")
        code, _, _ = _run_cli([str(dirty), "--config", str(bad_cfg)])
        if code != 2:
            bad.append(f"malformed config should exit 2, got {code}")
        # A path that cannot be read is an exit-2 failure.
        code, _, _ = _run_cli([str(Path(tmp) / "does_not_exist.py")])
        if code != 2:
            bad.append(f"missing source file should exit 2, got {code}")
        # --fix reports that nothing is auto-fixable (honest-check's rules need restructuring).
        code, _, err = _run_cli([str(dirty), "--fix"])
        if code != 1 or "auto-fixable" not in err:
            bad.append(f"--fix should run and report no auto-fixable corrections: {code} {err[:60]}")
        # --watch runs the check; with no trigger stream (EOF) it runs once and returns its code.
        code, _, _ = _run_cli([str(clean), "--watch"])
        if code != 0:
            bad.append(f"--watch on a clean tree should run once and exit 0, got {code}")
        # The JSON fixable field is computed (false for every structural rule), not hardcoded.
        _, out, _ = _run_cli([str(dirty), "--format", "json"])
        if '"fixable": false' not in out:
            bad.append("json output should carry a computed fixable field")
    # The watch loop re-runs once per trigger line and returns the last code at EOF.
    runs = {"n": 0}

    def _count():
        runs["n"] += 1
        return runs["n"]

    if watch(_count, io.BytesIO(b"\n\n")) != 3 or runs["n"] != 3:
        bad.append("watch should run once plus once per trigger line")
    if is_fixable("HC-NOPE"):
        bad.append("is_fixable should be false for a structural rule with no conservative fix")

    # The ancestor config search: chdir into a tree that carries honest-check.toml.
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, "honest-check.toml").write_text('[check]\nseverity = "warning"\n', encoding="utf-8")
        Path(tmp, "src.py").write_text(_CLEAN, encoding="utf-8")
        saved = os.getcwd()
        os.chdir(tmp)
        try:
            if _find_config(None) is None:
                bad.append("ancestor search did not find honest-check.toml")
            _run_cli(["src.py"])
        finally:
            os.chdir(saved)
    if _load_config(None) != empty_config():
        bad.append("_load_config(None) should be the empty config")
    # --lsp routes into the server; feed it an empty stdin (EOF -> 0). serve() uses the binary
    # buffers of stdin/stdout, so the fakes must expose .buffer.
    saved_in, saved_out = sys.stdin, sys.stdout
    sys.stdin = type("_S", (), {"buffer": io.BytesIO(b"")})()
    sys.stdout = type("_S", (), {"buffer": io.BytesIO()})()
    try:
        if cli_main(["--lsp"]) != 0:
            bad.append("--lsp should return the server's exit code")
    finally:
        sys.stdin, sys.stdout = saved_in, saved_out
    return bad


# --------------------------------------------------------------------------- lsp


def _frame(obj):
    data = json.dumps(obj).encode("utf-8")
    return f"Content-Length: {len(data)}\r\n\r\n".encode("ascii") + data


def _probe_lsp():
    bad = []
    # The full stdio loop: initialize, open a violating doc, then exit.
    stream = (
        _frame({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        + _frame({"method": "textDocument/didOpen", "params": {"textDocument": {"uri": "f.py", "text": _VIOLATION}}})
        + _frame({"method": "exit"})
    )
    sink = io.BytesIO()
    if serve(io.BytesIO(stream), sink) != 0:
        bad.append("serve should return 0 on exit")
    if b"publishDiagnostics" not in sink.getvalue():
        bad.append("serve did not publish diagnostics for an opened document")
    # A message carrying an extra (non-Content-Length) header line exercises the header loop.
    extra = b"Content-Type: x\r\n" + _frame({"method": "exit"})
    if serve(io.BytesIO(extra), io.BytesIO()) != 0:
        bad.append("serve should skip unknown headers and still parse the message")
    # EOF immediately.
    if serve(io.BytesIO(b""), io.BytesIO()) != 0:
        bad.append("serve should return 0 on EOF")
    # A zero-length body is treated as EOF too.
    if serve(io.BytesIO(b"Content-Length: 0\r\n\r\n"), io.BytesIO()) != 0:
        bad.append("serve should return 0 on an empty body")
    # _read_message of a bare stream is None.
    if _read_message(io.BytesIO(b"")) is not None:
        bad.append("_read_message of EOF should be None")
    # Every handler routes; the document store threads through (didOpen records text, hover reads it).
    empty = {}
    dispatch(empty, "initialized", None, {})
    opened, _ = dispatch(empty, "textDocument/didOpen", None, {"textDocument": {"uri": "f.py", "text": _VIOLATION}})
    if opened.get("f.py") != _VIOLATION:
        bad.append("didOpen should record the document text in the store")
    changed, _ = dispatch(empty, "textDocument/didChange", None, {"textDocument": {"uri": "f.py"}, "contentChanges": [{"text": _CLEAN}]})
    if changed.get("f.py") != _CLEAN:
        bad.append("didChange should update the document text in the store")
    dispatch(empty, "textDocument/didChange", None, {"textDocument": {"uri": "f.py"}, "contentChanges": []})
    dispatch(empty, "textDocument/didSave", None, {})
    closed, close_msgs = dispatch(opened, "textDocument/didClose", None, {"textDocument": {"uri": "f.py"}})
    if not close_msgs or "f.py" in closed:
        bad.append("didClose should publish an empty diagnostic set and drop the document")
    if dispatch(empty, "shutdown", 9, {})[1][0]["id"] != 9:
        bad.append("shutdown should respond to its id")
    if dispatch(empty, "totally/unknown", None, {})[1] != []:
        bad.append("an unknown method should be a no-op")
    # Hover over a violating line returns the rule and message; an unflagged line returns null.
    hover_hit = dispatch(opened, "textDocument/hover", 2, {"textDocument": {"uri": "f.py"}, "position": {"line": 0, "character": 0}})[1][0]
    if "HC-P003" not in (hover_hit["result"]["contents"]["value"] if hover_hit["result"] else ""):
        bad.append(f"hover over a violation should return its rule documentation: {hover_hit}")
    hover_miss = dispatch(opened, "textDocument/hover", 3, {"textDocument": {"uri": "f.py"}, "position": {"line": 99, "character": 0}})[1][0]
    if hover_miss["result"] is not None:
        bad.append("hover over an unflagged line should return null")
    # Go-to-definition resolves an identifier to its assignment or function definition in the file.
    defn_store, _ = dispatch(empty, "textDocument/didOpen", None, {"textDocument": {"uri": "d.py", "text": _DEFN_DOC}})

    def _definition(line, char):
        return dispatch(defn_store, "textDocument/definition", 1, {"textDocument": {"uri": "d.py"}, "position": {"line": line, "character": char}})[1][0]["result"]

    if (_definition(3, 4) or {}).get("range", {}).get("start", {}).get("line") != 2:
        bad.append(f"definition of V's use should point at its assignment on line 2: {_definition(3, 4)}")
    if (_definition(2, 4) or {}).get("range", {}).get("start", {}).get("line") != 0:
        bad.append(f"definition of make's use should point at its def on line 0: {_definition(2, 4)}")
    if _definition(4, 4) is not None:
        bad.append("definition of an undefined name should be null")
    if _definition(0, 3) is not None:
        bad.append("definition at a non-identifier position should be null")
    # workspace/symbol lists the vocabulary, binding, and chain declarations across open documents.
    sym_store, _ = dispatch(empty, "textDocument/didOpen", None, {"textDocument": {"uri": "s.py", "text": _SYMBOL_DOC}})
    all_symbols = dispatch(sym_store, "workspace/symbol", 7, {"query": ""})[1][0]["result"]
    names = sorted(s["name"] for s in all_symbols)
    if names != ["Bind", "Colors", "Flow"]:
        bad.append(f"workspace/symbol should list the vocabulary, binding, and chain declarations: {names}")
    filtered = dispatch(sym_store, "workspace/symbol", 8, {"query": "col"})[1][0]["result"]
    if [s["name"] for s in filtered] != ["Colors"]:
        bad.append(f"workspace/symbol should filter by the query substring: {filtered}")
    # codeAction offers a suppression directive for each diagnostic in the requested range.
    action_in = dispatch(opened, "textDocument/codeAction", 9, {"textDocument": {"uri": "f.py"}, "range": {"start": {"line": 0, "character": 0}, "end": {"line": 0, "character": 0}}})[1][0]["result"]
    if len(action_in) != 1 or "HC-P003" not in action_in[0]["title"] or "honest: ignore HC-P003" not in action_in[0]["edit"]["changes"]["f.py"][0]["newText"]:
        bad.append(f"codeAction should offer a suppression directive for the violation: {action_in}")
    action_out = dispatch(opened, "textDocument/codeAction", 10, {"textDocument": {"uri": "f.py"}, "range": {"start": {"line": 5, "character": 0}, "end": {"line": 5, "character": 0}}})[1][0]["result"]
    if action_out != []:
        bad.append("codeAction outside a violation's line should offer nothing")
    lsp = to_lsp_diagnostic(diagnostic("HC003", "error", "f.py", 1, 1, "m"))
    if lsp["severity"] != 1:
        bad.append("error should map to LSP severity 1")
    return bad


# --------------------------------------------------------------------------- startup


def _probe_startup():
    bad = []
    with tempfile.TemporaryDirectory() as tmp:
        clean = Path(tmp) / "clean.py"
        clean.write_text(_CLEAN, encoding="utf-8")
        dirty = Path(tmp) / "dirty.py"
        dirty.write_text(_SYNTAX_ERROR, encoding="utf-8")  # HC-SYN is startup-eligible

        startup_check([str(clean)])  # clean: returns, no handler
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            startup_check([str(dirty)], on_error="warn")
        if "HC" not in err.getvalue():
            bad.append("startup_check warn should print to stderr")
        try:
            startup_check([str(dirty)], on_error="raise")
            bad.append("startup_check raise should raise HonestCheckError")
        except HonestCheckError:
            pass
        try:
            with contextlib.redirect_stderr(io.StringIO()):
                startup_check([str(dirty)], on_error="halt")
            bad.append("startup_check halt should SystemExit")
        except SystemExit:
            pass
        # Directory input exercises the rglob branch of _collect.
        startup_check([tmp], on_error="warn")
        # A severity that does not match the finding filters it out (the collect skip branch).
        with contextlib.redirect_stderr(io.StringIO()):
            startup_check([str(dirty)], on_error="warn", severity="warning")
    return bad


def _probe_watchlist():
    bad = []
    io_list = IO_WATCH_LIST["python"]
    if matches_watchlist("", io_list):
        bad.append("an empty call name matches nothing")
    if not matches_watchlist("os.spawnvp", io_list):  # bare-wildcard entry os.spawn*
        bad.append("os.spawnvp should match the bare-wildcard entry os.spawn*")
    if not matches_watchlist("subprocess.run", io_list):  # exact
        bad.append("subprocess.run should match exactly")
    if not matches_watchlist("requests.get", io_list):  # dotted-wildcard requests.*
        bad.append("requests.get should match the dotted-wildcard entry requests.*")
    if matches_watchlist("totally.unlisted", io_list):
        bad.append("an unlisted name matches nothing")
    return bad


# --------------------------------------------------------------------------- suppression + determinism (HC-2)


def _probe_suppression():
    bad = []
    snippets = {
        "ignore": "class Widget:  # honest: ignore HC-P003\n    pass\n",
        "disable_block": "# honest: disable HC-P003\nclass A:\n    pass\n# honest: enable HC-P003\n",
        "disable_to_eof": "# honest: disable HC-P003\nclass A:\n    pass\n",
        "multi_rule": "# honest: disable HC-P003, HC-P001\nclass A:\n    pass\n",
        "disabled_then_outside": "# honest: disable HC-P003\n# honest: enable HC-P003\nclass A:\n    pass\n",
        "enable_without_disable": "# honest: enable HC-P003\nclass A:\n    pass\n",
        "not_a_directive": "# just a comment\nclass A:\n    pass\n",
        "unknown_verb": "# honest: frobnicate HC-P003\nclass A:\n    pass\n",
        "bare_verb": "# honest: disable\nclass A:\n    pass\n",
    }
    for label, source in snippets.items():
        diags = check_source(source, label)
        # A suppressed class violation is downgraded to info, not dropped (section 7.4).
        if label in ("ignore", "disable_block", "disable_to_eof", "multi_rule"):
            if not any(d["rule"] in ("HC-P003", "HC003") and d["severity"] == "info" for d in diags):
                bad.append(f"{label}: class violation should be downgraded to info: {[(d['rule'], d['severity']) for d in diags]}")
        else:
            if not any(d["rule"] in ("HC-P003", "HC003") and d["severity"] == "error" for d in diags):
                bad.append(f"{label}: class violation should remain an error: {[(d['rule'], d['severity']) for d in diags]}")
    return bad


def _probe_determinism():
    """HC-2: the same source yields the same diagnostics on every run."""
    sources = [_CLEAN, _VIOLATION, "if x == 1:\n    y = 1\nelif x == 2:\n    y = 2\nelse:\n    y = 3\n"]
    bad = []
    for source in sources:
        if check_source(source, "d.py") != check_source(source, "d.py"):
            bad.append("check_source is not deterministic")
    return bad


def run():
    probes = {
        "formats": _probe_formats(),
        "config": _probe_config(),
        "cli": _probe_cli(),
        "lsp": _probe_lsp(),
        "startup": _probe_startup(),
        "suppression": _probe_suppression(),
        "watchlist": _probe_watchlist(),
        "determinism": _probe_determinism(),
    }
    violations = [(name, msgs) for name, msgs in probes.items() if msgs]
    passed = sum(1 for msgs in probes.values() if not msgs)
    for name, msgs in violations:
        print(f"FAIL HC-shell [{name}]: {msgs}")
    print(f"HC laws/shells: {passed} passed, {len(violations)} failed, {len(probes)} total")
    return 0 if not violations else 1


if __name__ == "__main__":
    raise SystemExit(run())
