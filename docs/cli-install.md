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

To install a draft release candidate, use the `v1.0.0-draft` tag:

```bash
uv tool install "git+https://github.com/lesserevil/oompah@v1.0.0-draft"
pipx install "git+https://github.com/lesserevil/oompah@v1.0.0-draft"
```

Note: `v1.0.0-draft` is a force-movable tag. Reinstall it to pick up the
latest draft candidate.

## Install from a release wheel artifact

GitHub Releases attach wheel artifacts. You can install directly from the
artifact URL:

```bash
uv tool install "https://github.com/lesserevil/oompah/releases/download/v1.0.0/oompah-1.0.0-py3-none-any.whl"
pipx install "https://github.com/lesserevil/oompah/releases/download/v1.0.0/oompah-1.0.0-py3-none-any.whl"
```

## Verify the install

```bash
command -v oompah
oompah --help
oompah --version
oompah task --help
```

For a source-managed service deployment, the canonical operator command is
`$HOME/.local/bin/oompah` (normally `/home/shedwards/.local/bin/oompah`).
`oompah --version` prints the human-readable package version and full source
revision. The machine-readable `build_id` in `GET /healthz` and
`GET /api/v1/state` contains the same `name`, `version`, and `revision` fields.
The CLI and server revisions must match before task or admin requests are
used.

Normal source-managed lifecycle commands run the synchronization check before
starting or draining the service:

```bash
make start
make restart
make graceful
```

The check installs the exact clean, pushed `HEAD` revision into the canonical
UV tool and verifies both `command -v oompah` and `oompah --version`. A dirty,
unpushed, diverged, or failed install is refused before a running service is
interrupted. On an install failure, the known-good executable is restored and
the command prints the reason. After pushing the intended server revision,
recover with:

```bash
make install-cli
```

If that command reports a PATH error, put `$HOME/.local/bin` before project
virtualenv directories in `PATH`, then rerun `make install-cli`. Verify the
pair with `command -v oompah`, `oompah --version`, the public health check,
and an authenticated state request before retrying a lifecycle operation.

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

### Basic authentication

When the server is configured with `OOMPAH_HTPASSWD_FILE`, task and admin
requests, plus the protected API calls used by `make status`, `make restart`,
and `make graceful`, can authenticate with client-side credentials:

```bash
export OOMPAH_SERVER_USERNAME=operator
export OOMPAH_SERVER_PASSWORD_FILE=/run/secrets/oompah-client-password
oompah task view owner/repo#123
```

Use exactly one of `OOMPAH_SERVER_PASSWORD` (limited inline environment
alternative) or `OOMPAH_SERVER_PASSWORD_FILE` (preferred). A password file must be a regular,
readable file containing only the client plaintext password; symlinks are
rejected and group/world-readable POSIX files produce a warning. The CLI also
accepts the non-secret `--username` and `--password-file` options before the
subcommand. `--username` overrides `OOMPAH_SERVER_USERNAME`; `--password-file`
overrides both environment password sources. There is intentionally no
plaintext `--password` option. Do not put a password in `.env`, a URL, shell
history, or process arguments; use the password-file source for unattended
operation.

`OOMPAH_HTPASSWD_FILE` is server configuration and must contain htpasswd
password hashes. `OOMPAH_SERVER_PASSWORD` and `OOMPAH_SERVER_PASSWORD_FILE`
are client plaintext credential sources; they are not htpasswd files or server
configuration values. Never put credentials in `OOMPAH_SERVER_URL`.

#### Credential precedence

The task and admin CLIs use the same fixed source tiers: command-line options,
environment variables, then the default `~/.netrc` file. Tier 3, the netrc
fallback, is used only when a server URL can be resolved and no higher-priority
source supplies that value. If a default netrc file exists, it must still be
valid and safely permissioned.

**Username:** `--username` flag → `OOMPAH_SERVER_USERNAME` env → matching
`~/.netrc` entry → (none)

**Password:** `--password-file` flag → environment (`OOMPAH_SERVER_PASSWORD_FILE`,
then `OOMPAH_SERVER_PASSWORD`) → matching `~/.netrc` entry → (none)

**Rules:**
- Exactly one password source (set `OOMPAH_SERVER_PASSWORD_FILE` **or** `OOMPAH_SERVER_PASSWORD`, not both)
- Username required if password is set
- Password required if username is set
- No plaintext `--password` flag exists (security measure)
- A netrc entry must contain both `login` and `password`, and `~/.netrc` must
  be a non-symlink regular file with mode `600` or `400`

For netrc lookup, the CLI takes the hostname from `OOMPAH_SERVER_URL` (or
`--server`), removes its port, and lowercases it. Use the lowercased hostname
in the `machine` entry. IPv4 addresses are unchanged; write IPv6 addresses
without URL brackets. Thus `https://OOMPah.example.com:8443` selects `machine
oompah.example.com`, and `https://[2001:db8::1]:8443` selects `machine
2001:db8::1`. The machine value is matched exactly after this URL
normalization.

**Examples:**

Environment-based credentials (recommended for scripts):
```bash
export OOMPAH_SERVER_USERNAME=<username>
export OOMPAH_SERVER_PASSWORD_FILE=/path/to/password-file
oompah task view <task-id>
```

CLI flag override:
```bash
oompah task --username <username> --password-file /path/to/password-file view <task-id>
```

Default netrc credentials:
```bash
chmod 600 ~/.netrc
# ~/.netrc (keep outside the repository)
machine oompah.example.com
login <username>
password <password>

OOMPAH_SERVER_URL=https://oompah.example.com oompah task view <task-id>
```

Inline password (one-shot only, not for scripts):
```bash
# Controlled secret injection only; never use a command-line password.
OOMPAH_SERVER_USERNAME=<username> OOMPAH_SERVER_PASSWORD=<password> oompah task view <task-id>
# Environment values are preferable to arguments, but netrc/password files are safer for unattended use.
```

For complete setup, user management, password rotation, troubleshooting, and
security details, see [`docs/authentication.md`](authentication.md).

## Upgrading an existing install

If you installed oompah before the `project-bootstrap` subcommand was shipped,
your binary may lack the `project_bootstrap` module. Running
`oompah project-bootstrap status .` on a stale install fails with
`unrecognized arguments: status .` because the older `__main__.py` has no
project-bootstrap dispatch block.

Upgrade with either of these commands:

```bash
# Preferred: upgrade in place (uv tool)
uv tool upgrade oompah

# Alternative: force a full reinstall from the latest main branch
uv tool install --reinstall git+https://github.com/lesserevil/oompah

# pipx equivalent
pipx upgrade oompah
```

Then verify that the `project-bootstrap` subcommand is available:

```bash
oompah project-bootstrap --help
```

If `--help` prints the `status`, `preview`, and `apply` subcommands, the
upgrade was successful.

## Packaging design

See [`plans/cli-packaging-boundary.md`](../plans/cli-packaging-boundary.md) for
the decision record on why the CLI ships in the main `oompah` package rather
than as a separate `oompah-cli` package.

Maintainer release steps live in [`docs/cli-release.md`](cli-release.md).
