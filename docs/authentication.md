# HTTP Basic Authentication for Oompah

Oompah supports optional HTTP Basic authentication via Apache-style htpasswd files. This guide covers setup, configuration, user management, rotation, and recovery for operators.

## Overview

When enabled, Oompah requires HTTP Basic credentials (`username:password`) for:
- Dashboard web UI
- REST API endpoints
- WebSocket connections
- OpenAPI/Swagger documentation
- MCP gateway connections

**Unauthenticated (always accessible):**
- `GET /healthz` — health check endpoint with minimal metadata only
- `POST /api/v1/webhooks/github` — GitHub webhook delivery (GitHub signature validation still applies)
- `POST /api/v1/webhooks/gitlab` — GitLab webhook delivery (GitLab token validation still applies)

> **IMPORTANT:** HTTP Basic auth must always be used over HTTPS. Oompah does not terminate TLS itself — use a reverse proxy (nginx, HAProxy, Caddy, etc.) to terminate HTTPS and forward cleartext HTTP to Oompah.

## Configuration Quick Start

### 1. Generate a credential file

Use the standard `htpasswd` utility (Apache HTTP Server Tools):

```bash
# Create a new file with bcrypt password hashing (recommended)
htpasswd -B -c .htpasswd admin

# -B: use bcrypt ($2y$) hashing
# -c: create new file
# Interactive prompt for password (not shown on screen)
```

**On macOS** (if `htpasswd` is not installed):

```bash
# Install via Homebrew
brew install httpd

# Then:
$(brew --prefix)/bin/htpasswd -B -c .htpasswd admin
```

### 2. Add the file to your deployment

**For development (beside .env):**

```bash
cp .htpasswd ~/.oompah/  # or wherever you keep your .env file
```

Oompah auto-discovers `.htpasswd` beside the `.env` file — no configuration needed.

**For production (explicit path with secrets):**

```bash
# Store securely (e.g., Kubernetes secret, Docker secret, vault)
# Set the path in .env:
echo "OOMPAH_HTPASSWD_FILE=/run/secrets/htpasswd" >> .env

# Or provide via environment:
export OOMPAH_HTPASSWD_FILE=/run/secrets/oompah-htpasswd
oompah server
```

### 3. Restart Oompah

```bash
make restart
```

Oompah validates the htpasswd file at startup and **fails fatally** if it is missing, unreadable, malformed, empty, or contains plaintext passwords.

### 4. Verify auth is enabled

```bash
# Should print the healthz endpoint without credentials:
curl http://localhost:8080/healthz

# Should be rejected with 401 (WWW-Authenticate: Basic):
curl http://localhost:8080/api/v1/state

# Accepted with credentials:
curl -u admin:password http://localhost:8080/api/v1/state
```

---

## User Management

### Add a new user

```bash
# Add or update a user (prompts for password)
htpasswd .htpasswd operator

# -B: use bcrypt (automatically used if file already has bcrypt entries)
htpasswd -B .htpasswd operator
```

### Update a user's password

Same as add — htpasswd will overwrite the existing entry:

```bash
htpasswd .htpasswd admin
```

### Remove a user

```bash
# Use -D (delete) flag
htpasswd -D .htpasswd operator
```

### View htpasswd file contents

```bash
cat .htpasswd
# Output:
# admin:$2y$12$R9h/cIPz0gi.URNNGS3/aO/O.r6HS5xO31a5NQc6XjHPT8f6sFXe2
# operator:$2y$12$K8g/dJPz0fi.URNNGS4/bO/P.r7IS5xO31a5NQc6YjHPT8f6sGXf3
```

Usernames and bcrypt hashes are not sensitive — the file is safe to inspect. The plaintext password is never stored or logged.

---

## Password Rotation

When you change passwords or add/remove users:

1. **Edit the htpasswd file** (e.g., `htpasswd .htpasswd admin`)
2. **Restart Oompah** to load the new credentials:

```bash
make restart
```

(The normal `make restart` drains active agents before reloading credentials.)

**Important:** Credential changes require a restart. Oompah does not reload the htpasswd file on a signal or API call — you must restart the server process.

---

## Safe Disablement

To temporarily disable authentication (for local testing or manual recovery):

### Option 1: Remove the file

If using auto-discovery (.htpasswd beside .env):

```bash
rm .htpasswd
make restart
```

### Option 2: Clear OOMPAH_HTPASSWD_FILE

If using explicit configuration:

```bash
# In .env, comment out or delete:
# OOMPAH_HTPASSWD_FILE=/run/secrets/htpasswd

make restart
```

When Oompah starts with no configured htpasswd file and no .htpasswd beside .env, authentication is **disabled** and all routes are accessible without credentials.

---

## File Format and Hash Support

### Accepted formats

Oompah accepts **bcrypt** and **APR1** hashes only. Both are produced by `htpasswd`:

| Format   | Prefix | Example | htpasswd flag |
|----------|--------|---------|---|
| bcrypt   | `$2y$`, `$2b$`, `$2a$` | `$2y$12$R9h/cIP...` | `-B` (recommended) |
| APR1     | `$apr1$` | `$apr1$r31....$Hq...` | `-a apr1` |

### Rejected formats

- **Plaintext** (no algorithm prefix) — fatal error
- **SHA-1** (`$sha$`) — fatal error (deprecated)
- **MD5 crypt** (`$1$`) — fatal error (non-password context)
- **Other formats** — fatal error (fail-closed)

### Best practice

Always use bcrypt (`htpasswd -B`). It is modern, adaptive (cost can increase over time), and resistant to modern attacks.

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

**Fatal error.** Add at least one user: `htpasswd -B .htpasswd admin`.

---

## Client Configuration

### Prerequisite: Server-side and client-side are different

**Server stores hashes:**
- `OOMPAH_HTPASSWD_FILE` — Apache htpasswd file with password hashes (`bcrypt` or `APR1`)
- Server validates credentials at startup and requires restart for changes

**Clients need plaintext passwords:**
- `OOMPAH_SERVER_USERNAME` — client username (matches a name in htpasswd)
- `OOMPAH_SERVER_PASSWORD` or `OOMPAH_SERVER_PASSWORD_FILE` — client plaintext password (what you typed to `htpasswd`)

> Never put plaintext passwords or credentials in .env files, URLs, Makefile recipes, or logs. Always use environment variables or password files.

### CLI authentication

For `oompah task` commands:

```bash
export OOMPAH_SERVER_USERNAME=operator
export OOMPAH_SERVER_PASSWORD_FILE=/run/secrets/oompah-client-password

oompah task view owner/repo#123
```

**Password file format:** A regular file containing only the plaintext password (whitespace trimmed).

```bash
echo "my_plaintext_password" > /run/secrets/oompah-client-password
chmod 600 /run/secrets/oompah-client-password
```

### Makefile lifecycle commands

Commands like `make status`, `make restart`, and `make graceful` automatically use client credentials from the environment:

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
from httpx import BasicAuth, Client

username = os.environ["OOMPAH_SERVER_USERNAME"]
password = os.environ["OOMPAH_SERVER_PASSWORD"]

auth = BasicAuth(username, password)
with Client(auth=auth, base_url="http://localhost:8080") as client:
    resp = client.get("/api/v1/state")
    print(resp.json())
```

### curl examples

**With explicit username/password:**

```bash
curl -u admin:password http://localhost:8080/api/v1/state
```

**With password file (preferred):**

```bash
PASSWORD=$(cat /run/secrets/oompah-password)
curl -u admin:$PASSWORD http://localhost:8080/api/v1/state
```

Never use `curl -u admin:password http://...` with the password visible in shell history or process listings. Prefer password files or environment-based redaction.

### MCP Gateway

The MCP client (e.g., Claude Code's MCP integration) must provide credentials during the WebSocket handshake:

```bash
# MCP client connection (pseudo-code in your Claude Code settings.json):
{
  "mcp_servers": {
    "oompah": {
      "command": "... (MCP server command)",
      "env": {
        "OOMPAH_SERVER_USERNAME": "mcp-client",
        "OOMPAH_SERVER_PASSWORD_FILE": "/run/secrets/mcp-password",
        "OOMPAH_SERVER_URL": "http://localhost:8080"
      }
    }
  }
}
```

---

## Webhook Endpoints

GitHub and GitLab webhooks are **exempt from Basic auth** so that webhooks can be delivered without sending credentials to the webhook receiver.

### GitHub webhooks

Webhooks are delivered to: `POST /api/v1/webhooks/github`

- Basic auth is **not required** — GitHub can deliver webhooks without credentials
- GitHub signature validation (`X-Hub-Signature-256`) is **always enforced**, with or without Basic auth
- Webhook signature is your `webhook_secret` configured per project in `.oompah/projects.json`

### GitLab webhooks

Webhooks are delivered to: `POST /api/v1/webhooks/gitlab`

- Basic auth is **not required** — GitLab can deliver webhooks without credentials
- GitLab token validation (`X-Gitlab-Token`) is **always enforced**, with or without Basic auth
- Webhook token is your `webhook_secret` configured per project in `.oompah/projects.json`

### Webhook status

Checking webhook status requires authentication:

```bash
# Unauthenticated: 401
curl http://localhost:8080/api/v1/webhooks/gitlab/status

# Authenticated:
curl -u admin:password http://localhost:8080/api/v1/webhooks/gitlab/status
```

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
curl http://localhost:8080/healthz     # should work
curl http://localhost:8080/api/v1/state   # should be 401 if auth is on

# 2. Verify credentials are correct:
curl -u admin:password http://localhost:8080/api/v1/state

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

### "plaintext password" error at startup

**Symptom:** Oompah fails with: `htpasswd file:3: plaintext password (rejected; use bcrypt or APR1)`

**Cause:** The htpasswd file contains an entry without a hash algorithm prefix.

**Fix:**

1. Regenerate the file using `-B` flag:
   ```bash
   htpasswd -B -c .htpasswd admin
   ```

2. Or convert individual entries:
   ```bash
   # Bad: plaintext entry
   # admin:mypassword

   # Good: use htpasswd -B to add entries
   htpasswd -B .htpasswd admin
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
htpasswd -B .htpasswd admin
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
   cat $OOMPAH_SERVER_PASSWORD_FILE
   ```

3. Use an absolute path (relative paths may resolve differently depending on working directory).

### Lockout recovery

**Scenario:** You've lost the credentials or the htpasswd file is corrupted.

**Recovery:**

1. **Stop the server:**
   ```bash
   make stop
   ```

2. **Remove or disable the htpasswd file:**
   ```bash
   rm .htpasswd
   # OR comment out in .env:
   # OOMPAH_HTPASSWD_FILE=/run/secrets/htpasswd
   ```

3. **Restart without auth:**
   ```bash
   make start
   ```

4. **Regenerate credentials:**
   ```bash
   htpasswd -B -c .htpasswd admin
   ```

5. **Restart with auth enabled:**
   ```bash
   make restart
   ```

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

# Client credentials for task CLI and Makefile lifecycle commands.
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
- Credential file paths (only generic "not found" messages)
- Username/password distinction in verification errors (prevents user enumeration)

### Constant-time comparison

Password verification uses constant-time comparison to prevent timing attacks that might leak password length or character information.

### Fail-closed on startup

If htpasswd is invalid (malformed, empty, plaintext passwords, unsupported formats), **Oompah refuses to start**. This is intentional — better to fail loudly than to silently operate without auth when it was intended.

### Plaintext passwords in files only

Client credentials **may appear in `.env`, password files, or shell scripts** for deployment automation. These are ephemeral and necessary for unattended operation. But server htpasswd hashes and client plaintext passwords must never:
- Be committed to git
- Appear in logs or error messages
- Be embedded in URLs
- Be passed as command-line arguments
- Be shown in `ps` output

Use password files or secrets management (Kubernetes Secrets, Docker Secrets, HashiCorp Vault, AWS Secrets Manager) for production.

---

## Next Steps

1. **Generate credentials:** `htpasswd -B -c .htpasswd admin`
2. **Configure Oompah:** Place `.htpasswd` beside `.env` or set `OOMPAH_HTPASSWD_FILE`
3. **Restart:** `make restart`
4. **Verify:** `curl http://localhost:8080/healthz` should work; `curl http://localhost:8080/api/v1/state` should be 401
5. **Set up HTTPS:** Deploy behind nginx/HAProxy/Caddy with TLS termination
6. **Configure clients:** Set `OOMPAH_SERVER_USERNAME` and `OOMPAH_SERVER_PASSWORD_FILE` for CLI/MCP access

---

## See also

- `docs/operator-runbook.md` § Configuration — `.env` file reference
- `docs/cli-install.md` § Basic authentication — CLI credential setup
- `docs/project-bootstrap.md` — Project-specific authentication configuration
- `.env.example` — Complete configuration template
