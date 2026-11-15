"""The boundary layer: the readers and writers that touch the filesystem and the
streams (§3.1, §3.2, §6). I/O lives here; the pure resolvers (resolve_rule_config,
resolve_project_config, read_fault) build the records off what these read. A reader
hands the world's value on and asks nothing of the program."""

import fnmatch
import json
import sys
import tomllib
from pathlib import Path

from honest_design import read_hd
from honest_parse import language_of

from ._util import choose, pick, read_or

_EXTRA_SOURCE_SUFFIXES = (".ts", ".tsx")
_ADOPTION_LEVELS = {"Structural", "Boundary", "Typed", "Declared"}


def read_source(path):
    """Read one file's complete contents as raw bytes (§3.4). The reader on the
    filesystem side; it decodes nothing."""
    with open(path, "rb") as handle:
        return handle.read()


def _find_config():
    current = Path.cwd()
    candidates = [current] + list(current.parents)
    found = next(filter(lambda d: (d / "honest-check.toml").exists(), candidates), None)
    return pick(found is None, lambda: None, lambda: found / "honest-check.toml")


def _load_toml():
    path = _find_config()
    return pick(path is None, lambda: {}, lambda: tomllib.loads(path.read_text(encoding="utf-8")))


def load_config():
    """The raw [rules] table of the nearest-ancestor honest-check.toml, or the empty
    dict (§3.1). A thin reader: it hands the section on, building no record."""
    return read_or(_load_toml(), "rules", {})


def load_project_config():
    """The raw [check] table of the nearest-ancestor honest-check.toml, or the empty
    dict (§3.1). Distinct from load_config, which reads [rules]."""
    return read_or(_load_toml(), "check", {})


def resolve_rule_config(data):
    """Build the [rules] RuleConfig from the raw table: {"HC-OR003": {"min_run": N}}
    when the project set min_run, else the empty map (§3.1). Pure."""
    project = read_or(data, "HC-OR003", {})
    min_run = read_or(project, "min_run", None)
    return pick(min_run is None, lambda: {}, lambda: {"HC-OR003": {"min_run": min_run}})


def resolve_project_config(data):
    """Build the [check] ProjectConfig from the raw table, applying the documented
    defaults: exclude empty, adoption 'Declared', format_manifest empty (§3.1,
    §9.4). Pure."""
    raw_adoption = read_or(data, "adoption", "Declared")
    return {
        "exclude": read_or(data, "exclude", []),
        "adoption": choose(raw_adoption in _ADOPTION_LEVELS, raw_adoption, "Declared"),
        "format_manifest": read_or(data, "format_manifest", ""),
    }


def _recognized(path):
    return bool("ok" in language_of(path) or path.endswith(_EXTRA_SOURCE_SUFFIXES))


def _excluded(path, exclude):
    return any(
        fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(Path(path).name, pattern)
        for pattern in exclude
    )


def _keep(path, exclude):
    return bool(_recognized(path) and not _excluded(path, exclude))


def _walk_directory(directory, exclude):
    files = filter(lambda f: f.is_file(), directory.rglob("*"))
    kept = filter(lambda f: _keep(str(f), exclude), files)
    return [str(f) for f in kept]


def _discover_one(path, exclude):
    node = Path(path)
    return pick(
        node.is_dir(),
        lambda: _walk_directory(node, exclude),
        lambda: pick(
            node.is_file() and _keep(str(node), exclude),
            lambda: [str(node)],
            lambda: [],
        ),
    )


def discover_files(paths, exclude):
    """Walk each requested path, keeping every recognized source file no exclude glob
    matches; a directory is walked, a nonexistent or unrecognized path drops out
    (§3.2)."""
    out = []
    for path in paths:
        out.extend(_discover_one(path, exclude))
    return out


def write_report(text):
    """Print the already-rendered report to stdout and report that the write
    completed (§6). The CLI path's one output boundary."""
    print(text)
    return True


def pair_source(path, text):
    """Join a discovered path with its already-read bytes into a SourceFile, deciding
    nothing (§2.1)."""
    return {"path": path, "text": text}


def read_fault(reason):
    """Build honest-check's {problem, remedy} Fault from a raw read-failure reason
    (§HC-R002). Pure: the reader observed the failure; this assembles the record."""
    return {
        "problem": reason,
        "remedy": "correct the --declaration path, or fix the declaration so honest-design can parse it",
    }


def _parse_hd(hd_path, text):
    result = read_hd(text)
    return pick(
        "ok" in result,
        lambda: result["ok"]["modules"][0],
        lambda: f"honest-design could not parse {hd_path}: {read_or(result, 'err', 'unknown error')}",
    )


def read_declaration(hd_path):
    """Read the named .hd and parse it through honest-design's read_hd: the parsed
    Declaration on success, a raw str reason when the file is missing or will not
    parse (§2.1). The failure travels by return (§HC-R002)."""
    node = Path(hd_path)
    return pick(
        node.exists(),
        lambda: _parse_hd(hd_path, node.read_text(encoding="utf-8")),
        lambda: f"the --declaration path {hd_path} names no file",
    )


def _nearest_declaration_path(path):
    node = Path(path).resolve()
    found = next(
        filter(
            lambda p: p.name.startswith("honest-") and (p / f"{p.name}.hd").exists(),
            node.parents,
        ),
        None,
    )
    return pick(found is None, lambda: None, lambda: found / f"{found.name}.hd")


def discover_declaration(path):
    """The module Declaration governing one source file in base mode: its nearest
    enclosing honest-*/honest-*.hd read through read_declaration, or NOTHING when no
    module .hd governs it (§2.1 base-mode discovery, bead honest-framework-n64). A
    governing .hd that will not parse resolves to NOTHING too, so the door is not
    marked and its boundary finding stands rather than being dropped on a bad read."""
    hd_path = _nearest_declaration_path(path)
    parsed = pick(hd_path is None, lambda: None, lambda: read_declaration(str(hd_path)))
    return choose(hasattr(parsed, "keys"), parsed, None)


def _load_json(path):
    node = Path(path)
    return pick(node.exists(), lambda: json.loads(node.read_text(encoding="utf-8")), lambda: None)


def read_format_manifest(path):
    """honest-format's emitted vocabulary for a configured path, or the NOTHING arm
    (None) for an empty path or a manifest that cannot be read or parsed (§HC-REF004).
    The spec states no fault here, so the rule stands down rather than failing. The
    malformed-manifest catch lives here, at the reader door, not in an interior helper:
    a boundary is the one place an exception from the outside world is caught (P08)."""
    try:
        return pick(path == "", lambda: None, lambda: _load_json(path))
    except ValueError:
        return None
