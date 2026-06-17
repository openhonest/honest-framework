"""HTTP and CLI token extraction — the entry boundary into classification.

Both return `list[tuple[slot_name, raw_value]]`. The slot name is the
ingestion-time hint (e.g. form field name, CLI flag name); classify_token
adds the *type* by running recognizers. Binding later maps type → slot.
"""
from __future__ import annotations


def extract_http_tokens(request: dict) -> list[tuple[str, str]]:
    """Pure. Flatten a simplified HTTP request dict (path-params, query,
    form, json body) into (slot_name, value) pairs.

    `request` shape:
        { "path_params": dict[str,str],
          "query":       dict[str,str],
          "form":        dict[str,str],
          "json":        dict[str, any] }
    """
    out: list[tuple[str, str]] = []
    for source in ("path_params", "query", "form"):
        for k, v in (request.get(source) or {}).items():
            out.append((k, str(v)))
    for k, v in (request.get("json") or {}).items():
        out.append((k, str(v)))
    return out


def extract_cli_tokens(argv: list[str]) -> list[tuple[str, str]]:
    """Pure. Parse `--name=value`, `--name value`, and bare positionals.

    Positionals get slot names `arg0`, `arg1`, ...
    """
    out: list[tuple[str, str]] = []
    i = 0
    positional_idx = 0
    while i < len(argv):
        tok = argv[i]
        if tok.startswith("--"):
            body = tok[2:]
            if "=" in body:
                name, val = body.split("=", 1)
                out.append((name, val))
                i += 1
                continue
            # --name value
            name = body
            if i + 1 < len(argv) and not argv[i + 1].startswith("-"):
                out.append((name, argv[i + 1]))
                i += 2
            else:
                out.append((name, "true"))
                i += 1
        else:
            out.append((f"arg{positional_idx}", tok))
            positional_idx += 1
            i += 1
    return out
