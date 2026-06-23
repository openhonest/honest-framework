# honest-persist worked examples — the schema loaders

Two runnable todo apps that build their database schema from idiomatic models — one from
**Pydantic**, one from **Django** — and then drive the same honest-persist stack. They are adopter
code, not framework code: a `Schema` is plain data, and any mechanism that produces it is valid
(spec section 2.2), so these use ordinary model classes.

## Run them

From the `python/` workspace root:

```bash
uv run python honest-persist/examples/pydantic_todo.py
uv run python honest-persist/examples/django_todo.py
```

(Pydantic and Django are in the workspace dev dependency-group. An adopter would install
`honest-persist[pydantic]` or `honest-persist[django]`.)

## What they show

Each app:

1. **Defines models** — a `Todo` with a title and a `Literal["open","done"]` / `choices` status.
2. **Loads a `Schema`** — `load_schema_from_models(Todo)` or `load_schema_from_django(Todo)`.
3. **Migrates to real SQLite** — `migrate(schema, conn, "sqlite")`. The status compiles to an enum
   lookup table (`_hp_enum_todos_status`), seeded with its allowed values and enforced by a foreign
   key (spec section 6.1).
4. **Adds and completes todos** through the pure query builders (`insert`, `update`, `select`) and
   the `execute` boundary.
5. **Watches the enum reject an undeclared status** — the foreign key refuses `"archived"`.

## The point

`_app.py` holds the connection adapter and the demo. **Both apps call the same `run_todo_demo` with
their loaded schema, and produce a byte-identical schema and identical output** — because
honest-persist sees only the `Schema` dict. The loader it came from leaves no trace. A Django shop
and a FastAPI shop reach exactly the same place.

```
pydantic_todo.py ─┐
                  ├─ load_*  ──▶  identical Schema dict  ──▶  run_todo_demo (migrate + query)
django_todo.py  ──┘
```

The connection adapter (`SqliteConn` in `_app.py`) is the single I/O seam an adopter supplies — the
framework imports no database driver (spec section 8.1.1).
