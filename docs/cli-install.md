# Installing the oompah Task CLI

The `oompah` task CLI is distributed through **GitHub only** — there is no PyPI
release. Install it with `uv tool` or `pipx` directly from a GitHub tag or from
a release artifact wheel.

The default GitHub install is intentionally lightweight. It installs the
`oompah` console script, the `oompah task` subcommands, and the HTTP client
needed to talk to an existing oompah service. It does **not** install the
server runtime, create service configuration, or start an oompah service.

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

GitHub Releases attach wheel artifacts. You can install directly from the
artifact URL:

```bash
uv tool install "https://github.com/lesserevil/oompah/releases/download/v0.1.0/oompah-0.1.0-py3-none-any.whl"
pipx install "https://github.com/lesserevil/oompah/releases/download/v0.1.0/oompah-0.1.0-py3-none-any.whl"
```

## Verify the install

```bash
oompah --help
oompah task --help
```

## What you get

Both install paths provide the same entry point — the `oompah` binary. The
default install supports the task CLI without requiring the service runtime:

| Command | What it does |
|---------|--------------|
| `oompah --help` | Show CLI help |
| `oompah task <subcommand>` | Manage tasks in a running oompah server |

The `oompah task` subcommand is the one managed-project contributors and agents
use. It connects to a running oompah server (default port 8080) and does not
require local service configuration.

## Dependency isolation

`uv tool` and `pipx` install the package into an isolated virtual environment.
The default task CLI install only needs `httpx` plus the standard library, and
does **not** install server packages such as FastAPI, Uvicorn, Jinja, or
watchfiles.

## Running the service

Running the oompah service is a separate operator workflow. From a clone of the
oompah repository, install the server extra:

```bash
uv pip install -e '.[server]'
```

`make setup` does this for normal service development and operation. Managed
project contributors who only need `oompah task` do not need the server extra.

## Agent usage

Agents running inside a managed-project worktree use `oompah task` to interact
with the oompah server. The server URL defaults to `http://127.0.0.1:8080`;
override it with:

```bash
# Override the full server URL
OOMPAH_SERVER_URL=http://127.0.0.1:9000 oompah task view owner/repo#123

# Override just the port for a single command (server runs on localhost)
oompah task --port 9000 view owner/repo#123

# Override the full server URL for a single command
oompah task --server http://192.168.1.10:8080 view owner/repo#123
```

## Packaging design

See [`plans/cli-packaging-boundary.md`](../plans/cli-packaging-boundary.md) for
the decision record on why the CLI ships in the main `oompah` package rather
than as a separate `oompah-cli` package.

Maintainer release steps live in [`docs/cli-release.md`](cli-release.md).
