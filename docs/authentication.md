# HTTP Basic Authentication for Oompah

Oompah supports optional HTTP Basic authentication via Apache-style htpasswd
files. This guide covers setup, configuration, user management, rotation,
disablement, and recovery for operators.

> Authorization decisions for owner-gated mutations bind to the authenticated
> principal — see [authentication-identity-mapping.md](authentication-identity-mapping.md)
> for the htpasswd-user → project-actor mapping model and CLI migration guide.

> **HTTPS is mandatory.** HTTP Basic authentication only encodes credentials;
> it does not encrypt them. Put Oompah behind a TLS-terminating reverse proxy
> before enabling it for anything beyond a private local hop. Oompah does not
> terminate TLS itself.

## Overview

When enabled, Oompah requires HTTP Basic credentials (`username:password`) for:
- Dashboard web UI
- REST API endpoints
- WebSocket connections
- OpenAPI/Swagger documentation
- MCP gateway connections

**The only unauthenticated HTTP routes are:**

- `GET /healthz` — health check endpoint with minimal metadata only
- `POST /api/v1/webhooks/github` — GitHub webhook delivery (GitHub signature validation still applies)
- `POST /api/v1/webhooks/gitlab` — GitLab webhook delivery (GitLab token validation still applies)

Every other route is protected when authentication is enabled, including the
dashboard, REST API, OpenAPI (`/openapi.json`), WebSocket (`/ws`), MCP
discovery (`/.well-known/mcp`), MCP transport (`/api/mcp/v1`), and webhook
status (`/api/v1/webhooks/gitlab/status`). A different HTTP method, encoded
path, or path prefix is not an exemption.

## Public URL, TLS, and GitLab webhooks

These settings have separate jobs:

- `OOMPAH_GITLAB_WEBHOOK_PUBLIC_URL` is the public **Oompah** base URL that a
  GitLab instance can reach. GitLab delivers to
  `<base>/api/v1/webhooks/gitlab`; it is not the GitLab forge/API URL and it
  does not configure HTTP Basic authentication.
- TLS is terminated by the reverse proxy at that public URL. The proxy may
  forward to Oompah over a private loopback/network hop, but the public hop
  must be HTTPS.
- `OOMPAH_HTPASSWD_FILE` enables Basic authentication for Oompah's protected
  routes. It does not replace GitLab's `webhook_secret` or GitHub's webhook
  secret/signature configuration.

For GitLab setup, see [Project Bootstrap](project-bootstrap.md#webhook-configuration-public-https-endpoint-required).

## Configuration Quick Start

### 1. Generate a credential file

Use the standard `htpasswd` utility (Apache HTTP Server Tools):

```bash
# Run this from the directory containing the selected .env file.
# Create a new file with bcrypt password hashing (recommended).
umask 077
htpasswd -B -c .htpasswd operator
chmod 600 .htpasswd

# -B: use bcrypt ($2y$) hashing
# -c: create new file
# Interactive prompt for password (not shown on screen)
```

**On macOS** (if `htpasswd` is not installed):

```bash
# Install via Homebrew
brew install httpd

# Then:
$(brew --prefix)/bin/htpasswd -B -c .htpasswd operator
chmod 600 .htpasswd
```

### 2. Add the file to your deployment

**Beside the selected `.env` file (auto-discovery):**

```bash
# If the selected file is /srv/oompah/.env, use /srv/oompah as ENV_DIR.
ENV_DIR=/srv/oompah
umask 077
htpasswd -B -c "$ENV_DIR/.htpasswd" operator
chmod 600 "$ENV_DIR/.htpasswd"
```

With `OOMPAH_HTPASSWD_FILE` unset or empty, Oompah auto-discovers
`.htpasswd` beside the selected `.env` file. The file must be readable by the
service account and must not be committed; `.gitignore` already ignores
`.htpasswd` and `.htpasswd.*`, but verify the file is untracked before pushing.

**At an explicit secret path:**

```bash
# Store the file in a secret mount or other deployment secret store.
umask 077
htpasswd -B -c /run/secrets/oompah-htpasswd operator
chmod 600 /run/secrets/oompah-htpasswd

# Put this non-secret path in the selected .env, or inject it as an environment
# setting before starting the service:
OOMPAH_HTPASSWD_FILE=/run/secrets/oompah-htpasswd
```

An explicit relative value, such as `OOMPAH_HTPASSWD_FILE=secrets/oompah.htpasswd`,
is resolved relative to the selected `.env` directory. An absolute value is
used as written. An explicitly configured file must exist and be readable;
there is no fallback to auto-discovery when that path is wrong.

### 3. Restart Oompah

```bash
make restart
```

Oompah validates the htpasswd file at startup and **fails fatally** if it is missing, unreadable, malformed, empty, or contains plaintext passwords.

### 4. Verify auth is enabled

```bash
# Health is intentionally public and contains minimal metadata:
curl http://127.0.0.1:8080/healthz

# A protected route should return 401 (and a Basic challenge):
curl http://127.0.0.1:8080/api/v1/state

# Prompt for the password without putting it in shell history or argv. The
# username is non-secret; use the HTTPS proxy URL for remote access.
export OOMPAH_SERVER_USERNAME=operator
curl --user "$OOMPAH_SERVER_USERNAME:" https://oompah.example.com/api/v1/state
```

The last command prompts on the terminal because the password is omitted from
the `--user` value. For a non-interactive client, use the password-file
mechanism below rather than placing a password in a URL or command argument.

### Browser behavior

When an operator opens the dashboard or another protected page without
credentials, the browser receives `401 Unauthorized` and a Basic-auth prompt.
Enter the username and password there only over the HTTPS proxy. Browsers may
cache Basic credentials for the origin, so use a private operator profile on
shared machines and close it when finished; do not rely on browser logout as a
credential rotation mechanism. `GET /healthz` remains prompt-free, while the
webhook receivers are called by GitHub/GitLab with forge headers rather than
browser credentials.

---

## User Management

### Add a new user

```bash
# Add a user with bcrypt (prompts for the password; nothing is echoed).
htpasswd -B .htpasswd operator
chmod 600 .htpasswd
```

### Update a user's password

Same as add — htpasswd will overwrite the existing entry:

```bash
htpasswd -B .htpasswd operator
chmod 600 .htpasswd
```

### Remove a user

```bash
# Use -D (delete) flag
htpasswd -D .htpasswd operator
chmod 600 .htpasswd
```

Do not remove the last usable user unless you are intentionally disabling
authentication or have a recovery path. Add and verify a replacement user
before deleting the old one during a live rotation.

### Check the file without exposing its contents

```bash
stat -c '%a %U:%G %n' .htpasswd  # Linux; use stat -f on macOS
```

The file contains password hashes, but protect it as a credential file anyway:
do not print it into logs, tickets, terminals being recorded, or chat. The
plaintext password is never stored in the server htpasswd file.

---

## Password Rotation

Oompah reloads a changed htpasswd file during the next authenticated request;
a normal credential rotation does **not** require a restart or an
unauthenticated force restart. Create a complete replacement using your secret
manager or a protected staging file, then atomically rename it over the
configured regular file. Do not edit the live file in place.

```bash
# The staging file must be complete, mode 600, and on the same filesystem.
# Populate it with your secret-management procedure, not a shell transcript.
chmod 600 .htpasswd.next
mv -f .htpasswd.next .htpasswd

# First-party clients reread their client inputs from .env on each invocation.
make status
```

The replacement is read through a non-symlink file descriptor and parsed in
full before it becomes active. If it is missing, malformed, partial, a
symlink, or races the read, Oompah keeps the last known-good credentials and
continues requiring authentication. The protected `/api/v1/state` response
contains a redacted `http_auth.reload` status with `state`, `generation`, and
`retaining_last_known_good`; it never includes a path, usernames, hashes,
passwords, or parse details.

Restart only when changing whether authentication is configured at all (for
example, disabling auth or changing `OOMPAH_HTPASSWD_FILE`). A normal
`make restart` still drains active agents before restarting.

---

## Safe Disablement

To temporarily disable authentication (for local testing or manual recovery):

### Option 1: Move the discovered file

If using auto-discovery, move the file out of the discovered name while keeping
it recoverable and protected:

```bash
mv -f .htpasswd .htpasswd.disabled
chmod 600 .htpasswd.disabled
make restart
```

### Option 2: Clear OOMPAH_HTPASSWD_FILE

If using explicit configuration:

```bash
# In the selected .env, comment out or delete the non-secret path:
# OOMPAH_HTPASSWD_FILE=/run/secrets/htpasswd

make restart
```

When Oompah starts with no configured htpasswd file and no `.htpasswd` beside
the selected `.env`, authentication is **disabled** and all routes are
accessible without credentials. Treat this as a controlled maintenance or
rollback window: keep the service on a private interface, restore the file,
and restart promptly.

---

## File Format and Hash Support

### Accepted formats

Oompah accepts **bcrypt** and **APR1** hashes only. Both are produced by `htpasswd`:

| Format   | Prefix | Example | `htpasswd` guidance |
|----------|--------|---------|---|
| bcrypt   | `$2y$`, `$2b$`, `$2a$` | `<bcrypt-hash>` | `-B` (recommended) |
| APR1     | `$apr1$` | `<apr1-hash>` | `-m` on Apache implementations that emit APR1 |

### Rejected formats

- **Plaintext** (no algorithm prefix) — fatal error
- **SHA-1** (`$sha$`) — fatal error (deprecated)
- **MD5 crypt** (`$1$`) — fatal error (non-password context)
- **Other formats** — fatal error (fail-closed)

### Best practice

Always use bcrypt (`htpasswd -B`). It is modern, adaptive (cost can increase
over time), and resistant to modern attacks. APR1 is accepted only for
compatibility with existing files; do not create new APR1 credentials unless a
deployment requires them.

---

## Startup Behavior

### File present and valid

```
2026-07-28T01:00:00 INFO    oompah.http_auth Loaded HTTP Basic auth credentials from: .htpasswd
```

Authentication is **enabled**. All protected routes require credentials. Unauthenticated endpoints remain accessible.

### File absent (auto-discovery mode)

```
2026-07-28T01:00:00 DEBUG   oompah.http_auth No .htpasswd found beside env file; HTTP Basic auth disabled
```

Authentication is **disabled**. All routes are accessible without credentials.

### File missing but explicitly configured

```
2026-07-28T01:00:00 CRITICAL oompah.http_auth Configured OOMPAH_HTPASSWD_FILE not found: /run/secrets/htpasswd
... service startup FAILED
```

**Fatal error.** Restart Oompah with a valid file path, or remove/comment the configuration.

### File is malformed

```
2026-07-28T01:00:00 CRITICAL oompah.http_auth htpasswd file /path/.htpasswd:3: plaintext password (rejected; use bcrypt or APR1)
... service startup FAILED
```

**Fatal error.** Regenerate the file using `htpasswd -B .htpasswd username`.

### File is empty or contains only comments/blanks

```
2026-07-28T01:00:00 CRITICAL oompah.http_auth htpasswd file has no valid entries: /path/.htpasswd
... service startup FAILED
```

**Fatal error.** Add at least one user: `htpasswd -B .htpasswd operator`.

---

## Client Configuration

### Prerequisite: Server-side and client-side are different

**Server stores hashes:**
- `OOMPAH_HTPASSWD_FILE` — Apache htpasswd file with password hashes (`bcrypt` or `APR1`)
- Server validates credentials at startup and safely reloads complete atomic replacements

**Clients need plaintext passwords:**
- `OOMPAH_SERVER_USERNAME` — client username (matches a name in htpasswd)
- `OOMPAH_SERVER_PASSWORD_FILE` — preferred path to a regular file containing
  the client plaintext password (what you typed to `htpasswd`)
- `OOMPAH_SERVER_PASSWORD` — limited inline environment alternative for a
  short-lived shell or controlled secret injection; do not put it in a
  committed `.env`, URL, command argument, or process-managed config

> Never put plaintext passwords or credentials in URLs, command arguments,
> logs, documentation, or source control. Password files should be regular,
> owner-readable files with mode `600` where the platform permits it.

### CLI Credential Precedence

The `oompah task` and `oompah admin` CLIs resolve credentials using a fixed
priority order. This section documents the exact precedence so you can predict
which source will be used when multiple are configured.

At the source level, both values use the same tiers: command-line options,
environment variables, then the default `~/.netrc` file. Tier 3, `~/.netrc`,
is the fallback value when no higher-priority source supplies that value. The
CLI can use this fallback only when it can resolve a server URL. If a default
netrc file exists, it must still be valid and safely permissioned.

**Username resolution (highest priority first):**
1. CLI flag: `--username <username>`
2. Environment variable: `OOMPAH_SERVER_USERNAME`
3. Matching `~/.netrc` entry for the server hostname
4. (none) — unauthenticated if no password source is set

**Password resolution (highest priority first):**
1. CLI flag: `--password-file <path-to-password-file>`
2. Environment variables: `OOMPAH_SERVER_PASSWORD_FILE`, then
   `OOMPAH_SERVER_PASSWORD` (inline)
3. Matching `~/.netrc` entry for the server hostname
4. (none) — unauthenticated if no username source is set

**Configuration rules:**
- Username is required if any password source is set
- Password is required if username is set
- Exactly one password source must be configured; both `OOMPAH_SERVER_PASSWORD` and `OOMPAH_SERVER_PASSWORD_FILE` cannot be set together (error)
- `~/.netrc` entries must provide both `login` and `password`; the file must
  be a regular, non-symlink file with mode `600` or `400`
- Return value: `ClientCredentials(username, password)` if configured, or `None` for backward-compatible unauthenticated mode

**Security emphasis:**
- Never pass plaintext passwords via the `--password` flag (no such flag exists)
- Prefer `~/.netrc` or password files (`OOMPAH_SERVER_PASSWORD_FILE` or
  `--password-file`) for unattended use; set password-file permissions to
  mode `600`
- `OOMPAH_SERVER_PASSWORD` is limited to interactive shells and controlled secret injection (do not put in `.env` files)
- Command-line passwords are process-visible in `ps` output. Oompah has no
  plaintext `--password` option; do not work around that safeguard with shell
  arguments, URLs, or command substitution.

#### Netrc hostname selection

For the default `~/.netrc` fallback, the CLI extracts the hostname from the
resolved `OOMPAH_SERVER_URL` (or `--server` value), removes the port, and
converts the hostname to lowercase before lookup. Use that normalized value in
the `machine` line: DNS hostnames must be lowercase; IPv4 addresses are used
as written; and an IPv6 address is written without URL brackets. For example,
`https://OOMPah.example.com:8443` looks up `machine oompah.example.com`, while
`https://[2001:db8::1]:8443` looks up `machine 2001:db8::1`. Netrc machine
names are matched exactly after URL normalization, so an uppercase `machine`
name will not match.

#### Examples

**Default netrc credentials (recommended when one user contacts the same server):**
```bash
chmod 600 ~/.netrc
# ~/.netrc; keep this file outside the repository
machine oompah.example.com
login <username>
password <password>

OOMPAH_SERVER_URL=https://oompah.example.com oompah task view <task-id>
```

**Unattended operation with password file (recommended):**
```bash
export OOMPAH_SERVER_USERNAME=<username>
export OOMPAH_SERVER_PASSWORD_FILE=/path/to/password-file
oompah task view <task-id>
```

**Override environment with CLI flags:**
```bash
# Environment says one thing, CLI flags override it:
export OOMPAH_SERVER_USERNAME=<default-username>
export OOMPAH_SERVER_PASSWORD_FILE=/path/to/default-password-file

# These flags take precedence:
oompah task --username <override-username> --password-file /path/to/override-password-file view <task-id>
```

**Inline password for a single short-lived command (not for committed scripts):**
```bash
# Limited use: controlled secret injection only
export OOMPAH_SERVER_USERNAME=<username>
export OOMPAH_SERVER_PASSWORD=<password>
oompah task view <task-id>
unset OOMPAH_SERVER_PASSWORD  # Clear immediately
```

**Makefile lifecycle commands:**
Commands like `make status`, `make restart`, and `make graceful` respect the
same credential precedence:
```bash
export OOMPAH_SERVER_USERNAME=<username>
export OOMPAH_SERVER_PASSWORD_FILE=/path/to/password-file
make status
make graceful
```

### CLI authentication

For `oompah task` commands:

```bash
export OOMPAH_SERVER_USERNAME=operator
export OOMPAH_SERVER_PASSWORD_FILE=/run/secrets/oompah-client-password

oompah task view owner/repo#123
```

**Password file format:** A regular file containing only the plaintext password (whitespace trimmed).

```bash
# Read without echoing, write without placing the value in shell history/argv.
CLIENT_PASSWORD_FILE=/run/secrets/oompah-client-password
umask 077
read -r -s -p 'Oompah client password: ' CLIENT_PASSWORD
printf '\n'
printf '%s\n' "$CLIENT_PASSWORD" > "$CLIENT_PASSWORD_FILE"
unset CLIENT_PASSWORD
chmod 600 "$CLIENT_PASSWORD_FILE"
```

Set `OOMPAH_SERVER_USERNAME` and `OOMPAH_SERVER_PASSWORD_FILE` in the client
environment, or pass the non-secret CLI overrides:

```bash
export OOMPAH_SERVER_USERNAME=operator
export OOMPAH_SERVER_PASSWORD_FILE=/run/secrets/oompah-client-password
oompah task view owner/repo#123
```

The CLI precedence is: `--username` over `OOMPAH_SERVER_USERNAME`, and
`--password-file` over both environment password forms. Without the CLI file
override, set exactly one of `OOMPAH_SERVER_PASSWORD_FILE` or
`OOMPAH_SERVER_PASSWORD`; both is an error. There is deliberately no
plaintext `--password` option. The first-party task and admin CLIs reread
these client inputs from the current `.env` on each operator invocation, so
update the client password-file reference before making the first request with
a rotated password. Spawned workers do not receive or reload Basic credentials;
they use only their scoped task-handoff capability.

### Makefile lifecycle commands

Commands like `make status`, `make restart`, and `make graceful` automatically
refresh client credentials from the current `.env` and use them for protected
lifecycle requests:

```bash
export OOMPAH_SERVER_USERNAME=operator
export OOMPAH_SERVER_PASSWORD_FILE=/run/secrets/oompah-client-password

make status
make graceful
```

### Python SDK / httpx client

For custom scripts using httpx:

```python
import os
from pathlib import Path
from httpx import BasicAuth, Client

username = os.environ["OOMPAH_SERVER_USERNAME"]
password_file = os.environ["OOMPAH_SERVER_PASSWORD_FILE"]
password = Path(password_file).read_text(encoding="utf-8").strip()

auth = BasicAuth(username, password)
with Client(auth=auth, base_url="https://oompah.example.com") as client:
    resp = client.get("/api/v1/state")
    print(resp.json())
```

For a local-only process-to-service hop, a loopback `http://` URL is also
possible. Never use that form for a network-facing client. If the password
file is unavailable, the limited alternative is to set
`OOMPAH_SERVER_PASSWORD` in the process environment for that invocation and
unset it immediately afterward; do not put its value in source or argv.

### curl examples

**Interactive prompt (no password in history or argv):**

```bash
export OOMPAH_SERVER_USERNAME=operator
curl --user "$OOMPAH_SERVER_USERNAME:" https://oompah.example.com/api/v1/state
```

When curl sees a username with no password, it prompts on the terminal. For
automation, use a protected netrc/config file supplied by your secret manager
and pass only its path to curl:

```bash
NETRC_FILE=/run/secrets/oompah-netrc
chmod 600 "$NETRC_FILE"
curl --netrc-file "$NETRC_FILE" https://oompah.example.com/api/v1/state
```

The netrc file is a client secret and must be provisioned outside the
repository; do not print it or commit it. Do not use a `--user
user:password` argument, command substitution in a `--user` argument, or a
URL containing credentials.

### MCP Gateway

MCP uses the embedded streamable-HTTP transport, not a separate MCP password.
The generic MCP client must connect to the discovered endpoint
`/.well-known/mcp` / `/api/mcp/v1` over HTTPS and provide the same Basic
credentials during its HTTP handshake. Configure the client with a protected
password-file reference rather than a literal password:

```bash
# Generic MCP client configuration (adapt the key names to your client):
{
  "mcpServers": {
    "oompah": {
      "url": "https://oompah.example.com/api/mcp/v1",
      "env": {
        "OOMPAH_SERVER_USERNAME": "mcp-client",
        "OOMPAH_SERVER_PASSWORD_FILE": "/run/secrets/oompah-mcp-password"
      }
    }
  }
}
```

The exact names for URL and secret-file references vary by MCP client; the
security requirements do not. Use `GET /.well-known/mcp` to inspect discovery
metadata after authenticating. It reports `authentication: "http-basic"`
when enabled. MCP does not expose webhook ingestion or lifecycle-control
tools, and the Basic boundary still protects the transport and discovery.

---

## Webhook Endpoints

GitHub and GitLab webhooks are **exempt from Basic auth** so that webhooks can be delivered without sending credentials to the webhook receiver.

### GitHub webhooks

Webhooks are delivered to: `POST /api/v1/webhooks/github`

- Basic auth is **not required** — GitHub can deliver webhooks without credentials
- GitHub signature validation (`X-Hub-Signature-256`) remains separate from
  Basic auth and is checked when the matching project has a `webhook_secret`
- Configure a per-project `webhook_secret` so signed delivery is enforced;
  the handler supports an initial setup window for a matching project with no
  secret, which must not be treated as a secure steady state

### GitLab webhooks

Webhooks are delivered to: `POST /api/v1/webhooks/gitlab`

- Basic auth is **not required** — GitLab can deliver webhooks without credentials
- GitLab token validation (`X-Gitlab-Token`) is **always enforced**, with or without Basic auth
- The token is the per-project `webhook_secret` configured through the project
  settings/API; a matching project without one is rejected with 401

### Webhook status

Checking webhook status requires authentication:

```bash
# Unauthenticated: 401
curl https://oompah.example.com/api/v1/webhooks/gitlab/status

# Authenticated: prompt for the password without putting it in argv.
export OOMPAH_SERVER_USERNAME=operator
curl --user "$OOMPAH_SERVER_USERNAME:" \
  https://oompah.example.com/api/v1/webhooks/gitlab/status
```

Webhook delivery itself uses the forge signature/token headers, not Basic
credentials. The status endpoint is an ordinary protected API route.

---

## Reverse Proxy Setup

> **CRITICAL:** Never expose Oompah to the Internet over HTTP. HTTP Basic auth sends credentials in Base64 encoding (easily decoded). Always use HTTPS with a reverse proxy that terminates TLS.

### Example: nginx

```nginx
server {
    listen 443 ssl http2;
    server_name oompah.example.com;

    ssl_certificate /etc/ssl/certs/oompah.crt;
    ssl_certificate_key /etc/ssl/private/oompah.key;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    location / {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;

        # Do not add credentials to this configuration. The proxy forwards
        # the client's Authorization header only when the client supplied it.

        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}

# Redirect HTTP → HTTPS
server {
    listen 80;
    server_name oompah.example.com;
    return 301 https://$server_name$request_uri;
}
```

### Example: HAProxy

```
global
    log stdout local0
    mode http

frontend public
    bind *:443 ssl crt /etc/ssl/certs/oompah.pem
    bind *:80
    redirect scheme https if !{ ssl_fc }
    default_backend oompah

backend oompah
    balance roundrobin
    server localhost 127.0.0.1:8080 check
```

---

## Troubleshooting

### 401 "Authentication required"

**Symptom:** Requests are rejected with HTTP 401.

**Check:**

```bash
# 1. Verify auth is enabled:
curl https://oompah.example.com/healthz       # should work
curl https://oompah.example.com/api/v1/state  # should be 401 if auth is on

# 2. Verify credentials interactively (password is prompted, not shown):
export OOMPAH_SERVER_USERNAME=operator
curl --user "$OOMPAH_SERVER_USERNAME:" \
  https://oompah.example.com/api/v1/state

# 3. Check oompah logs:
make logs | grep -i auth
```

### "htpasswd file not found"

**Symptom:** Oompah fails to start with error: `Configured OOMPAH_HTPASSWD_FILE not found: /run/secrets/htpasswd`

**Solution:**

1. Check file path in `.env`:
   ```bash
   grep OOMPAH_HTPASSWD_FILE .env
   ```

2. Verify file exists and is readable:
   ```bash
   ls -la /run/secrets/htpasswd
   ```

3. If using secrets management, ensure the secret is mounted before Oompah starts.

4. If using auto-discovery, verify `.htpasswd` is beside `.env`:
   ```bash
   ls -la .env .htpasswd
   ```

5. Check that the service account can read the file and that its mode is
   restrictive:
   ```bash
   chmod 600 .htpasswd
   ```

### "plaintext password" error at startup

**Symptom:** Oompah fails with: `htpasswd file:3: plaintext password (rejected; use bcrypt or APR1)`

**Cause:** The htpasswd file contains an entry without a hash algorithm prefix.

**Fix:**

1. Regenerate the file using `-B` flag:
   ```bash
   umask 077
   htpasswd -B -c .htpasswd operator
   chmod 600 .htpasswd
   ```

2. Recreate or update individual entries with bcrypt:
   ```bash
   htpasswd -B .htpasswd operator
   chmod 600 .htpasswd
   ```

3. Restart:
   ```bash
   make restart
   ```

### "htpasswd file has no valid entries"

**Symptom:** Oompah fails with: `htpasswd file has no valid entries: /path/.htpasswd`

**Cause:** The file is empty or contains only comments/blank lines.

**Fix:**

```bash
htpasswd -B .htpasswd operator
chmod 600 .htpasswd
make restart
```

### Password file permission warning

**Symptom:** Client logs show:
```
WARNING oompah.client_auth OOMPAH_SERVER_PASSWORD_FILE '/path/to/password' has unsafe permissions 0o644
```

**Fix:**

```bash
chmod 600 /path/to/password
```

Group/world-readable password files are a security risk. The warning does not block operation (to support container secrets that use permissive modes), but restricting permissions is recommended.

### "Cannot access OOMPAH_SERVER_PASSWORD_FILE: No such file"

**Symptom:** CLI commands fail with: `Cannot access OOMPAH_SERVER_PASSWORD_FILE '/path/to/password': No such file`

**Fix:**

1. Verify the path:
   ```bash
   ls -la $OOMPAH_SERVER_PASSWORD_FILE
   ```

2. Ensure it's readable by the user running the command:
   ```bash
   test -r "$OOMPAH_SERVER_PASSWORD_FILE"
   stat -c '%a %U:%G %n' "$OOMPAH_SERVER_PASSWORD_FILE"  # Linux
   ```

3. Use an absolute path (relative paths may resolve differently depending on working directory).

### Lockout recovery

**Scenario:** You've lost the credentials or the htpasswd file is corrupted.

**Recovery:**

1. **Stop the server:**
   ```bash
   make stop
   ```

2. **Temporarily move or disable the htpasswd file (preserve it for rollback):**
   ```bash
   mv -f .htpasswd .htpasswd.disabled
   chmod 600 .htpasswd.disabled
   # OR comment out in .env:
   # OOMPAH_HTPASSWD_FILE=/run/secrets/htpasswd
   ```

3. **Restart without auth:**
   ```bash
   make start
   ```

4. **Regenerate credentials:**
   ```bash
   umask 077
   htpasswd -B -c .htpasswd operator
   chmod 600 .htpasswd
   ```

5. **Restart with auth enabled:**
   ```bash
   make restart
   ```

If the service uses an explicit secret mount, restore or recreate that mount
instead of creating a discovered `.htpasswd`. Verify the protected endpoint
with the client password file before re-enabling normal external traffic. If
the file is corrupted, replace the complete file atomically according to the
secret-store's procedure; do not edit a live secret in a shell transcript.

---

## Auth Health Dashboard Signals

The Oompah dashboard exposes separate health indicators for the two
authentication planes.  These appear as compact badges under a collapsible
"Authentication health" banner whenever a plane is degraded.

### Operator auth plane (HTTP Basic)

| Badge | Meaning |
|-------|---------|
| **Operator auth: ✓** (green) | No recent 401 failures. Credentials are accepted. |
| **Operator auth: ⚠ N** (amber) | N failed Basic-auth requests in the last 15 min. |

**Recovery:** Update `.htpasswd` (regenerate with `htpasswd -B`) and run
`make restart` to reload credentials.  The badge clears automatically once the
15-minute window passes without new failures.

### Worker token plane (task-handoff capability)

| Badge | Meaning |
|-------|---------|
| **Worker token: —** (grey) | No token has been minted yet. No workers dispatched. |
| **Worker token: ✓** (green) | Token minted and accepted; no recent failures. |
| **Worker token: ⚠ N** (amber) | N missing-token or cross-scope failures in the last 15 min. |

**Missing-token failures (401):** The worker did not receive or forward
`OOMPAH_TASK_HANDOFF_TOKEN`.  Check that `agent_environment()` is applied to
every spawned subprocess environment.

**Cross-scope failures (403 scope):** The worker presented a token scoped to a
different project or task identifier.  Verify `OOMPAH_TASK_HANDOFF_PROJECT_ID`
matches the project of the dispatched task.

**Intentional action denials (403 action):** The worker requested an action
not included in the capability grant (e.g., a tracker operation not in the
allowed-actions set).  These are expected least-privilege denials and are
**never** surfaced as auth-health warnings.

---

## Configuration Reference

### Environment variables

| Variable | Default | Description |
|----------|---------|---|
| `OOMPAH_HTPASSWD_FILE` | (auto-discovery) | Path to htpasswd file. Empty/unset: try `.htpasswd` beside `.env`. Relative: resolve against `.env` directory. Absolute: use as-is. |
| `OOMPAH_SERVER_USERNAME` | (unset) | Client username for HTTP Basic auth. Required if any password source is set. |
| `OOMPAH_SERVER_PASSWORD` | (unset) | Client plaintext password (inline). Set exactly one of this or `OOMPAH_SERVER_PASSWORD_FILE`. |
| `OOMPAH_SERVER_PASSWORD_FILE` | (unset) | Path to file containing client plaintext password (preferred). Set exactly one of this or `OOMPAH_SERVER_PASSWORD`. |

### .env example

```bash
# =====================================================================
# HTTP Basic Authentication (optional, OOMPAH-521 epic)
# =====================================================================

# Path to Apache-style htpasswd file.
# Auto-discovery: .htpasswd beside .env (if unset or empty)
# Explicit: absolute or relative to .env directory
# OOMPAH_HTPASSWD_FILE=.htpasswd

# Client credentials for task CLI and Makefile lifecycle commands. These are
# client-side settings; do not put a plaintext value in this file.
# Prefer OOMPAH_SERVER_PASSWORD_FILE over OOMPAH_SERVER_PASSWORD.
# OOMPAH_SERVER_USERNAME=operator
# OOMPAH_SERVER_PASSWORD_FILE=/run/secrets/oompah-password
```

---

## Security Considerations

### Secrets are never leaked

Oompah and its CLI clients **never** log, display, or echo:
- Authorization headers
- Plaintext passwords
- Password-file contents or htpasswd hashes
- Username/password distinction in verification errors (prevents user enumeration)

Startup diagnostics may identify the configured path so an operator can repair
permissions or mounts. Protect service logs and do not treat a path as a
secret-bearing substitute for the file itself.

### Constant-time comparison

Password verification uses constant-time comparison to prevent timing attacks that might leak password length or character information.

### Fail-closed on startup

If htpasswd is invalid (malformed, empty, plaintext passwords, unsupported formats), **Oompah refuses to start**. This is intentional — better to fail loudly than to silently operate without auth when it was intended.

### Plaintext password sources

The preferred client source is a protected password file or deployment secret.
The inline environment form is a limited alternative for a short-lived shell
or controlled secret injection; do not store it in a committed `.env` or shell
script. Server htpasswd hashes and client plaintext passwords must never:
- Be committed to git
- Appear in logs or error messages
- Be embedded in URLs
- Be passed as command-line arguments
- Be shown in `ps` output

Use password files or secrets management (Kubernetes Secrets, Docker Secrets, HashiCorp Vault, AWS Secrets Manager) for production.

---

## Next Steps

1. **Generate credentials:** `umask 077; htpasswd -B -c .htpasswd operator; chmod 600 .htpasswd`
2. **Configure Oompah:** Place `.htpasswd` beside `.env` or set `OOMPAH_HTPASSWD_FILE`
3. **Restart:** `make restart`
4. **Verify:** `curl https://oompah.example.com/healthz` should work; the protected state route should be 401 without credentials
5. **Set up HTTPS:** Deploy behind nginx/HAProxy/Caddy with TLS termination
6. **Configure clients:** Set `OOMPAH_SERVER_USERNAME` and `OOMPAH_SERVER_PASSWORD_FILE` for CLI/MCP access

---

## See also

- `docs/operator-runbook.md` § Configuration — `.env` file reference
- `docs/cli-install.md` § Basic authentication — CLI credential setup
- `docs/project-bootstrap.md` — Project-specific authentication configuration
- `docs/scoped-task-cli-authentication.md` — How service-launched agents
  authenticate with a scoped, short-lived task capability instead of the
  operator's Basic credentials
- `.env.example` — Complete configuration template
