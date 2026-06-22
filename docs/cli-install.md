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
uv tool install "git+https://github.com/lesserevil/oompah@v1.0.0"

# pipx
pipx install "git+https://github.com/lesserevil/oompah@v1.0.0"
```

Replace `v1.0.0` with the tag listed on the
[GitHub Releases page](https://github.com/lesserevil/oompah/releases).

## Install from a release wheel artifact

GitHub Releases attach wheel artifacts. You can install directly from the
artifact URL:

```bash
uv tool install "https://github.com/lesserevil/oompah/releases/download/v1.0.0/oompah-1.0.0-py3-none-any.whl"
pipx install "https://github.com/lesserevil/oompah/releases/download/v1.0.0/oompah-1.0.0-py3-none-any.whl"
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
| `oompah project-bootstrap <subcommand>` | Inspect or apply oompah's managed-project bootstrap templates |

The `oompah task` subcommand is the one managed-project contributors and agents
use. It connects to a running oompah server (default port 8080) and does not
require local service configuration.

The `oompah project-bootstrap` subcommand can be used by project owners to
create or refresh baseline `AGENTS.md`, `docs/`, `plans/`, Makefile, and
githook scaffolding from oompah's bundled templates. See
[`project-bootstrap.md`](project-bootstrap.md).

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
with the oompah server. Set **`OOMPAH_SERVER_URL`** to point the CLI at the
correct server — this is the stable, canonical way to configure the server
location:

```bash
export OOMPAH_SERVER_URL="http://127.0.0.1:8080"
oompah task view <task-id>
```

The default when `OOMPAH_SERVER_URL` is unset is `http://127.0.0.1:8080`.

> **Note:** `OOMPAH_SERVER_PORT` is a *service* configuration variable that
> controls which port the oompah server listens on. It is **not** a client-side
> server locator — setting it in an agent environment has no effect on where
> `oompah task` sends requests. Use `OOMPAH_SERVER_URL` instead.

See [`docs/cli-api-surface.md`](cli-api-surface.md) for the full 1.0
compatibility surface, including the stable `oompah task` subcommands and what
managed-project `AGENTS.md` files may safely depend on.

## Compatibility surface

The stable 1.0 CLI and API surface — the commands and environment variables that
managed-project `AGENTS.md` files may depend on — is documented in
[`docs/cli-api-surface.md`](cli-api-surface.md).

## Packaging design

See [`plans/cli-packaging-boundary.md`](../plans/cli-packaging-boundary.md) for
the decision record on why the CLI ships in the main `oompah` package rather
than as a separate `oompah-cli` package.

Maintainer release steps live in [`docs/cli-release.md`](cli-release.md).
