# Secret redaction and rotation runbook

Oompah persists agent activity to per-agent JSONL logs, the console
transcript store, and the service log stream. Every one of those sinks
runs through a **central redaction boundary** that scrubs known secret
patterns (HTTP Basic passwords, bearer tokens, API keys, URLs with
userinfo, credential dataclass fields, ...) before writing to disk or
fanning out to WebSocket / state-API consumers. Callers that need to
extend the redaction rules edit
[`oompah/secrets.py`](../oompah/secrets.py) — see `SECRET_KEYS` and
`SECRET_PATTERNS`.

This document is for operators who need to:

* audit past logs for a secret exposure incident, or
* rotate a leaked credential the code fixes cannot un-persist.

## Sinks covered by redaction

| Sink                                                   | Redacted at                                              | File                              |
|--------------------------------------------------------|----------------------------------------------------------|-----------------------------------|
| Per-agent JSONL (ACP: Claude / Codex / OpenCode)        | `orchestrator._on_event`                                 | `oompah/orchestrator.py`          |
| Per-agent JSONL (api_agent)                            | `ApiAgentSession._log_event`                             | `oompah/api_agent.py`             |
| State API `AgentActivity.summary` / `detail` / `usage` | `orchestrator._on_event`, `ApiAgentSession._emit`        | `oompah/orchestrator.py`, `oompah/api_agent.py` |
| `SessionState.last_message`                            | `orchestrator._on_event` (derived from redacted payload) | `oompah/orchestrator.py`          |
| Console transcript (new path)                          | `ConsoleSession._persist_and_emit`, `ConsoleEvent.to_dict` | `oompah/console.py`, `oompah/console_format.py` |
| Console transcript (legacy path)                       | `ConsoleStore.append`                                    | `oompah/console_legacy.py`        |
| Console WebSocket broadcast                            | inherits from `ConsoleStore.append` / `_persist_and_emit`| both console modules              |
| Service logger (`oompah.*` namespace)                  | `SecretRedactionFilter`                                  | `oompah/secrets.py` (installed by `__main__`) |

The redaction is **fail-closed** on unknown-type objects: any value that
reaches the terminal fallback in `redact_sensitive_data` is rendered
via `repr()`/`str()` and scanned for secrets *before* being returned.
Downstream `json.dumps(..., default=str)` cannot bypass the scrub.

## Auditing existing logs for exposure

Before rotating a credential, confirm whether it made it to disk.
Search the persistence roots for the plaintext value **from a workstation
that already holds the credential**; do not paste it into oompah task
comments, GitHub issues, or chat.

```bash
# Adjust paths for your deployment.
OOMPAH_HOME=${OOMPAH_HOME:-$HOME/.oompah}

# Per-agent JSONL (ACP / api_agent) — one file per agent run.
grep -R --binary-files=text -l 'YOUR_SECRET_HERE' \
  "$OOMPAH_HOME"/logs \
  "$OOMPAH_HOME"/agents 2>/dev/null

# Console transcripts.
grep -R --binary-files=text -l 'YOUR_SECRET_HERE' \
  "$OOMPAH_HOME"/console 2>/dev/null

# Service log (if journalctl-managed, use journalctl --grep).
grep --binary-files=text 'YOUR_SECRET_HERE' \
  "$OOMPAH_HOME"/service.log 2>/dev/null
```

Do **not** copy any hits into an oompah task, chat message, or ticket.
Refer to them by file path + byte offset only. Redaction is now in place
for future writes, but historical logs written before this fix landed
may still contain plaintext.

## Cleaning historical logs

If an audit turns up plaintext, either:

1. **Rotate then delete.** Preferred. Once the credential is rotated
   (see below), the plaintext in old logs is inert. Delete or truncate
   the affected files at your normal log-retention cadence.

2. **Redact in place.** If retention policy forbids deletion, run a
   one-off scrub before rotating. The tool is `sed -i` with the exact
   sentinel; do not use pattern-based scrubs against production logs
   without a dry run:

   ```bash
   # DRY RUN first.
   grep -R --binary-files=text -c 'YOUR_SECRET_HERE' "$OOMPAH_HOME"

   # Then in-place scrub.
   grep -Rl --binary-files=text 'YOUR_SECRET_HERE' "$OOMPAH_HOME" | \
     xargs -I {} sed -i 's/YOUR_SECRET_HERE/[REDACTED]/g' {}
   ```

## Rotating a leaked credential

The exact rotation ceremony depends on where the credential lives.
Common cases oompah cares about:

| Credential                                | Where it lives                                                       | Rotation                                                                      |
|-------------------------------------------|----------------------------------------------------------------------|-------------------------------------------------------------------------------|
| `OOMPAH_SERVER_PASSWORD` (task-handoff)   | `.env` on the oompah host                                            | Generate new value, update `.env`, `make graceful`. Old value stops accepting immediately (single-value config). |
| `OOMPAH_SERVER_PASSWORD_FILE` (task-handoff, file-mode) | Path referenced by `.env`                                    | Overwrite the file atomically (`install -m 600 new_value old_path`), then `make graceful`. |
| Provider API key (Claude / Codex / OpenAI-compatible) | `.env` or provider-specific config                        | Rotate in the provider console → update `.env` → `make graceful`. |
| Task tracker token (GitHub / GitLab)      | `.env` (`OOMPAH_GITHUB_TOKEN` / `OOMPAH_GITLAB_TOKEN`)               | Revoke old token in the provider UI, mint new one, update `.env`, `make graceful`. |
| Persisted database credential             | `.env` or downstream service config                                  | Rotate in the database, update `.env`, `make graceful`. |

`make graceful` drains active agents before restarting and re-reads
configuration — this is the safe path for credential rotation. Use
`make force-restart` only if `make graceful` refuses to drain.

## Verifying the fix

After a rotation, confirm no future writes leak the new value:

```bash
# Restart the service.
make graceful

# Wait for at least one agent dispatch, then re-run the audit search.
# Expect zero hits for the new plaintext.
grep -R --binary-files=text -l 'NEW_SECRET_HERE' "$OOMPAH_HOME"/logs \
  "$OOMPAH_HOME"/agents "$OOMPAH_HOME"/console 2>/dev/null
```

If a new hit appears, file a `type:bug priority:1` task naming the file
path (never the plaintext) and page the security owner; something is
bypassing the central redaction boundary and must be closed at the
source before further rotations.
