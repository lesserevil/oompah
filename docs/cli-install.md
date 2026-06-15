# Installing the oompah CLI

The `oompah` CLI is distributed through **GitHub only** — there is no PyPI
release.  Install it with `uv tool` or `pipx` directly from a GitHub tag or
from a release artifact wheel.

## Quick install (latest main branch)

```bash
uv tool install git+https://github.com/lesserevil/oompah
```

or with pipx:

```bash
pipx install git+https://github.com/lesserevil/oompah
```

## Install a specific release tag

```bash
# uv tool (recommended)
uv tool install "git+https://github.com/lesserevil/oompah@v0.1.0"

# pipx
pipx install "git+https://github.com/lesserevil/oompah@v0.1.0"
```

Replace `v0.1.0` with the tag listed on the
[GitHub Releases page](https://github.com/lesserevil/oompah/releases).

## Install from a release wheel artifact

When a GitHub Release is published (see [#313](https://github.com/lesserevil/oompah/issues/313)),
wheel artifacts are attached.  You can install directly from the artifact URL:

```bash
uv tool install "https://github.com/lesserevil/oompah/releases/download/v0.1.0/oompah-0.1.0-py3-none-any.whl"
```

## Verify the install

```bash
oompah --help
oompah task --help
```

## What you get

Both install paths provide the same entry point — the `oompah` binary — which
exposes two surfaces:

| Command | What it does |
|---------|--------------|
| `oompah` | Start the oompah orchestration server |
| `oompah task <subcommand>` | Manage tasks in a running oompah server |

The `oompah task` subcommand is the one managed-project contributors and agents
use most.  It connects to a locally-running oompah server (default port 8080)
and does not require any of the server libraries at runtime.

## Dependency isolation

`uv tool` and `pipx` install the package into an isolated virtual environment.
The ~120 transitive packages (fastapi, uvicorn, jinja2, etc.) required by the
oompah server live in that private env and do **not** pollute your project
environment or system Python.

## Agent usage

Agents running inside a managed-project worktree use `oompah task` to interact
with the oompah server.  The server URL defaults to `http://127.0.0.1:8080`;
override it with:

```bash
OOMPAH_SERVER_PORT=9000 oompah task view owner/repo#123
# or
oompah task --port 9000 view owner/repo#123
```

## Packaging design

See [`plans/cli-packaging-boundary.md`](../plans/cli-packaging-boundary.md) for
the decision record on why the CLI ships in the main `oompah` package rather
than as a separate `oompah-cli` package.
