# CLI Packaging Boundary Decision

**Status:** Decided — keep in main package  
**Issue:** lesserevil/oompah#317  
**Epic:** lesserevil/oompah#312 — Distribute the oompah CLI through GitHub releases

## Background

The `oompah` console script currently lives in the main `oompah` package alongside
the full orchestration server. Issue #317 asks whether managed-project contributors
who only need `oompah task` should install a slimmer package instead.

## Current Dependency Footprint

Running `uv tree` against the main package shows **~122 transitive packages**
dominated by the server stack:

| Direct dependency | Role |
|-------------------|------|
| `fastapi` + `pydantic` + `starlette` | HTTP API server |
| `uvicorn[standard]` | ASGI server runner |
| `jinja2` + `python-liquid` | Template rendering |
| `pyyaml` | YAML config/workflow parsing |
| `watchfiles` | Workflow file hot-reload |
| `httpx` | HTTP client (also used by `oompah task`) |
| `PyJWT[crypto]` + `cryptography` | GitHub webhook validation |
| `python-multipart` | Form parsing |

The `oompah task` subcommand (`oompah/task_cli.py`) is already well-isolated:
it only imports `stdlib` modules plus an optional `httpx`. Everything else is
lazy-imported by the server path.

A hypothetical `oompah-cli` slim package would have exactly one non-stdlib
dependency: `httpx`.

## Options Evaluated

### Option A — Keep in main package (chosen)

`uv tool install git+https://github.com/lesserevil/oompah` (or a tagged release
artifact) installs the full package in an isolated tool environment. Users get
both the `oompah` server binary and the `oompah task` subcommand from one install.

**Pros:**
- Zero extra maintenance: one package, one release workflow, one version number.
- `oompah task` always ships in lock-step with the server it talks to — no
  version-skew risk.
- `uv tool` / `pipx` isolate the dependency tree; the extra ~120 packages go into
  a private venv and do not pollute the managed project environment.
- `task_cli.py` is already cleanly separated; a future split is low-risk if the
  footprint ever becomes a real blocker.

**Cons:**
- Slightly heavier download on first install (~3–5 MB extra for the server libs).
- Agents that only need `oompah task` pull in fastapi/uvicorn/etc. they never use.

### Option B — Split into `oompah-cli` or `oompah-task`

A new package containing only `task_cli.py` + `httpx`, published separately.

**Pros:**
- Leaner install for contributors who only need `oompah task`.

**Cons:**
- Two packages to build, tag, release, and keep in sync.
- Version skew risk: `oompah-cli@0.1.1` talking to `oompah@0.1.0` could break on
  API changes.
- Splitting `task_cli.py` out of the `oompah` package requires moving or
  re-exporting it; the `oompah.__main__` dispatch path would need updating.
- Adds friction for contributors wanting the full server.

## Decision: Option A — Keep in main package

The footprint penalty (~120 extra packages in an isolated `uv tool` venv) is
acceptable given:

1. `uv tool` and `pipx` fully isolate the install — no pollution of the managed
   project environment.
2. Maintenance overhead of two packages outweighs the disk/bandwidth saving.
3. `task_cli.py` is already cleanly separated and easy to split later if the
   need becomes concrete.

The install path for managed-project contributors is documented in
[`docs/cli-install.md`](../docs/cli-install.md).

## Future Split Trigger

Revisit this decision if any of the following become true:

- The full package install time becomes a meaningful blocker for agent cold-starts.
- A new server dependency significantly increases the footprint (e.g., numpy/torch).
- PyPI distribution is added and bandwidth costs matter at scale.

File a follow-up under epic #312 when that threshold is reached.
