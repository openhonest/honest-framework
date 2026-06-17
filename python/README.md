# Honest Framework — Python implementations

Status as of this checkpoint:

| Module | Tests | Status |
|---|---|---|
| honest-gherkin | 21 | M1 complete |
| honest-type | 23 | M1 complete (foundation) |
| honest-observe | 14 | M1 complete |
| honest-persist | 15 | M1 complete (SQLite; Turso pluggable) |
| honest-check | 13 | M1 complete (HC-P001, HC-P003, HC-P014) |
| honest-test | 13 | M1 complete |
| honest-state | 11 | M1 complete |
| honest-features | 15 | M1 complete |
| honest-alerts | 10 | M1 complete |
| honest-page | 12 | M1 complete (server-side primitives) |
| honest-dom | 6  | M1 (server-side types; client JS TBD) |
| honest-components | 23 | M1 complete (includes the component runtime) |
| **Total** | **176** | **12 FOSS modules** |

FOSS theming is the component runtime's startup merge of component `style.json` defaults plus honest-page's `--ht-` tokens and `light-dark()`. The component runtime (discovery, organism mount, CSS-namespace enforcement, grid assembly, startup token merge) is honest-components' reference implementation — folded in from the former standalone package. honest-errors is a standalone leaf utility composed by honest-observe and honest-alerts (see `specs/02-code-quality/honest-errors-architecture.md`).

## Running a module's tests

```bash
cd python/honest-<module>
PYTHONPATH="$(pwd)/src" python3 -m pytest tests/ -p no:cacheprovider
```

## Running all tests at once

```bash
cd python
for mod in honest-*/; do
  abs_src="$(pwd)/$mod/src"
  mod_name=$(basename "$mod")
  out=$(cd "$mod" && PYTHONPATH="$abs_src" python3 -m pytest tests/ -p no:cacheprovider -q 2>&1 | tail -1)
  echo "  $mod_name: $out"
done
```

## Honest-code compliance

All FOSS modules follow the principles:
- No classes (except TypedDict / Protocol / Exception subclasses). Enforceable via honest-check HC-P003.
- Dict-lookup polymorphism — no if/elif/else discriminant dispatch. Enforceable via HC-P001.
- I/O only at boundaries (cli.py, connection.py, log.py).
- Pure functions for all core logic.
- Step handlers and event folds take state in, return new state — no mutation.

## What's M1 and what's not

M1 (shipped here):
- Core types + constructors + pure transforms
- Happy path + error-path tests
- Boundary helpers (sqlite, file I/O where required)

Not in M1:
- CLI entry points for every module (only honest-gherkin, honest-check, honest-type have `cli.py`)
- Turso (pyturso) replacement for SQLite in honest-persist — trivial swap at the `connect()` boundary
- Client-side JS for honest-DOM (domx library) — Python provides only the server-side types
- Visual / design-time authoring surface — out of scope for this standard
- Gherkin feature files for every module beyond honest-gherkin smoke

## Existing scaffold

The root of `python/` (`app.py`, `templates/`, `static/`) is the original
honest-py demo scaffold — a FastAPI application showing how the pieces
wire together at the HTTP + DOM surface. The per-module packages below
(`python/honest-*/`) are the framework implementations those demos are
built on.

## Next M2 priorities

1. Wire honest-gherkin feature files to run automatically per module (use `example` declarations from the `.hd` files as scenario sources).
2. honest-check rules HC-R001 through HC-OR003 from the spec.
3. Exception-to-fault boundary policy at HTTP entry (honest-page).
4. Pyturso swap in honest-persist.
5. domx library in JS.
