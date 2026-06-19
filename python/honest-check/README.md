# honest-check

The static linter that enforces Honest Code. Point it at your source and it flags
the structural dishonesty the framework eliminates: classes that hide state,
if/elif/else value-dispatch, I/O performed off the boundary, exceptions caught in
business logic, and the rest. Any code it passes is, by definition, structurally
Honest Code.

This README is for **using** the linter. How the rules work internally is in
[`../CONTRIBUTING.md`](../CONTRIBUTING.md).

## Install

honest-check is a package in the framework's uv workspace. From the workspace root
(`python/`):

```sh
uv sync
```

That makes the `honest-check` command available through `uv run`.

## Run it

```sh
# Check a file or a directory (directories are searched recursively for .py)
uv run honest-check src/

# Check the current directory
uv run honest-check
```

Exit codes are CI-ready:

- `0` — no errors
- `1` — one or more errors (the build should fail)
- `2` — could not run (bad config, unreadable source)

## Output formats

Choose with `--format`:

```sh
uv run honest-check src/ --format human    # default, for a terminal
uv run honest-check src/ --format json     # machine-readable
uv run honest-check src/ --format github   # GitHub Actions annotations
uv run honest-check src/ --format junit    # JUnit XML for CI test reports
```

Filter what is shown:

```sh
uv run honest-check src/ --severity error      # hide warnings and info
uv run honest-check src/ --rule HC-P003        # run only this rule (repeatable)
uv run honest-check src/ --no-rule HC-P006     # suppress this rule (repeatable)
```

`--severity` changes what is *displayed*; the exit code still reflects whether any
error-level diagnostics were found.

## Configuration

Drop a `honest-check.toml` at your project root. honest-check searches the current
directory and its ancestors, or pass `--config <path>` to point at one explicitly.

```toml
[check]
paths    = ["src/"]                              # what to check when no path is given
exclude  = ["**/migrations/**", "**/__pycache__/**"]   # glob patterns to skip
severity = "warning"                             # minimum severity to display

[rules]
disable  = ["HC-P006"]                           # rules to switch off project-wide
```

Command-line flags win over the file: a `--severity` or path on the command line
overrides the same setting in `honest-check.toml`.

## Suppressing a rule in source

When a line legitimately needs an exception (a declared I/O boundary, a primitive
input-contract guard), annotate it with a `# honest:` comment. The directive must
be a real comment, never inside a docstring.

```python
result = do_io()          # honest: ignore HC-P002      one line only

# honest: disable HC-P001                               start of a block
...
# honest: enable HC-P001                                end of the block

# honest: disable HC-P001, HC-P003                      several rules at once
```

A `disable` with no matching `enable` holds to the end of the file. Suppressions
are a deliberate, auditable record of where and why an exception was taken; reach
for the narrowest scope that works.

## As a pre-commit gate

The framework repo wires honest-check into a pre-commit hook so dishonest code
cannot land. To do the same in your project, run honest-check over your staged
sources and block the commit on a non-zero exit. The repo's own `lint-all.sh` and
`lint-affected.sh` show the shape.

## Editor integration (LSP)

honest-check speaks the Language Server Protocol over stdio, so an editor can show
diagnostics as you type:

```sh
uv run honest-check --lsp
```

Point your editor's LSP client at that command for Python files.

## License

Apache-2.0.
