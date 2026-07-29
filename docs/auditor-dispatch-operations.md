# Independent Auditor Dispatch — Operations Guide

This guide is for operators running Oompah with independent auditor dispatch enabled. It covers configuration, monitoring, troubleshooting, and recovery for the audit queue system.

**See also:** `plans/independent-auditor-dispatch.md` (design and architecture)

The priority lane is enabled by default. It scans persisted `In Validation`
requests on each dispatch tick and shares the global worker pool with ordinary
implementation agents.

## Overview

When enabled, the lane consumes audit requests staged as a task moves toward
a terminal state (Done, Merged, or Archived). The coordinator moves the task
to `In Validation`; the independent auditor dispatch lane then:

1. Reads queued audit requests from tasks in `In Validation`
2. Selects an independent auditor (provider/model not used by the task's contributors)
3. Launches a reserved auditor agent with read-only verification tools
4. Handles retry and rotation if the auditor's provider is unavailable or busy
5. Routes exhausted audits (no remaining candidates) to `Needs Human` with configuration guidance

## Configuration

### Environment Variables

These `.env` settings control the dispatch lane.

#### Core Auditor Settings

```bash
# Maximum number of auditor candidates to attempt per audit before
# routing to Needs Human when all independent candidates fail.
# Recommended: 3-5 (allows several independent candidates to be tried).
OOMPAH_AUDIT_MAX_ATTEMPTS=3

# Time-to-live (seconds) for running auditor attempts.
# A live auditor session older than this is considered abandoned and eligible
# for retry. An attempt with no live worker is reclaimed immediately.
# Recommended: 3600 (1 hour). Set higher for slower CI environments.
OOMPAH_AUDIT_ATTEMPT_TTL=3600

# Relative ordering among In Validation audits without an explicit task
# priority. The audit lane still runs before ordinary Open work when a slot is
# available. Recommended: 100-200.
OOMPAH_AUDIT_PRIORITY=100

# Maximum number of In Validation tasks scanned per scheduler tick.
# Limits the audit lane's CPU time per tick to avoid blocking work dispatch.
# Recommended: 32-64. Set to 0 for no limit (scan all pending audits).
OOMPAH_AUDIT_LANE_SCAN_LIMIT=32
```

#### Global Settings That Affect Auditors

These existing settings also apply to auditor dispatch:

```bash
# Global agent concurrency limit (affects both workers and auditors).
# Auditors consume from this same pool. Increase if you want more
# parallelism for audits + work.
OOMPAH_MAX_CONCURRENT_AGENTS=5

# Budget limit (auditors count against this).
# If you want unlimited audit attempts regardless of budget, set
# a high limit for completion verification work.
OOMPAH_BUDGET_LIMIT=50.00

# Retry backoff settings (same for audits and normal work).
# Auditor provider/tool failures use the normal exponential delay before
# rotating to the next candidate.
OOMPAH_MAX_RETRY_BACKOFF_MS=300000
```

### Auditor Role Configuration

The auditor role defines which providers/models are eligible auditors. It is configured in `.oompah/roles.json`:

```json
{
  "name": "auditor",
  "strategy": "round_robin",
  "candidates": [
    { "provider_id": "prov-deep", "model": "claude-opus-4" },
    { "provider_id": "prov-standard", "model": "claude-sonnet-4" },
    { "provider_id": "prov-fast", "model": "gpt-4o" }
  ],
  "updated_at": "2026-01-01T12:00:00Z"
}
```

**Candidate order:**

The audit lane considers candidates in the saved role order and excludes every
provider/model pair already attempted by that audit. A retry therefore rotates
to the next eligible pair. The role's `strategy` field remains part of the
shared role configuration, but the audit lane does not apply round-robin usage
history.

**Adding candidates:**

1. Via dashboard: Navigate to the Roles section and edit the auditor role.
2. Via API: use `GET /api/v1/roles` to inspect the current matrix and
   `PUT /api/v1/roles` to save the complete role payload. The standard roles
   (`fast`, `standard`, `deep`, and `default`) are required; `auditor` is an
   optional multi-candidate row. See `docs/multi-provider-roles.md` for the
   request shape and validation rules.

**Provider independence check:**

Before each audit, Oompah verifies that the selected auditor provider is independent from the task's contributors:

- If contributors used `prov-fast/gpt-4o`, then `prov-fast/gpt-4o` is skipped.
- If contributors used `prov-standard` with unknown model (ACP SDK-managed), then all `prov-standard` candidates are skipped (fail-closed).
- If only dependent candidates remain, the audit is routed to `Needs Human`
  with the `no_auditor` failure classification.

## Monitoring

### Dashboard

When the lane is enabled, the Oompah dashboard displays:

- **In Validation tasks**: count and list under the "In Validation" column.
- **Running audits**: active auditor agents shown in the "Active Agents" section.
- **Audit metrics**: dispatch lane statistics in the metrics sidebar.

### Logs

Use the project Make target to watch the service log:

```bash
# Tail the service log in real time
make logs

# Example output:
# [INFO] audit dispatch: starting audit-1 (task OOMPAH-123) on prov-fast/gpt-4, candidate rotation 0
# [INFO] audit dispatch: auditor exit (audit-1) — transient failure, rotating to next candidate
# [INFO] audit dispatch: rotation failed — no independent candidates; routing to Needs Human
```

### State and Metrics

The supported diagnostics endpoint is `/api/v1/state`. Audit counters are
available under `orchestrator_metrics.audits`, and running auditor rows include
their audit and attempt IDs.

```bash
# Inspect current dispatch metrics
curl -s http://localhost:8080/api/v1/state | jq '.orchestrator_metrics.last_dispatch'

# Audit fields exposed in the same state snapshot:
{
  "audits": {
    "pending_count": 3,
    "in_progress_count": 2,
    "dispatch_count": 45,
    "exhaustion_count": 1
  }
}
```

## Troubleshooting

### "No Independent Auditor Candidates" Error

The audit was routed to `Needs Human` because all auditor candidates used the same providers as the task's contributors.

**Solutions:**

1. **Add more providers to the auditor role**: Edit `.oompah/roles.json` to add candidates from different providers.

   ```json
   {
     "candidates": [
       { "provider_id": "prov-external", "model": "gpt-4-turbo" },
       { "provider_id": "prov-internal", "model": "claude-opus" }
     ]
   }
   ```

2. **Configure a provider whitelist for auditors** (future): Pin the auditor role to specific independent providers.

3. **Reopen the task with different contributors** (workaround): If the same contributors will work again, start the task with `deep` or other non-default profiles to change the provider pool.

### Auditor Rate-Limited (HTTP 429)

The selected provider returned a rate-limit error. Oompah persists the failed
attempt, waits for the normal exponential retry backoff, and then rotates to
the next independent candidate.

**If rotations keep failing:**

1. Check provider health: Dashboard → Providers → check rate-limit status.
2. Increase the provider's quota or throttle limit in the provider configuration.
3. Add more independent providers to the auditor role.
4. Increase `OOMPAH_MAX_RETRY_BACKOFF_MS` only if the provider needs a longer
   cooldown before the next attempt.

### Auditor Timeout (Took Too Long)

The auditor took longer than `OOMPAH_AGENT_COMMAND_TIMEOUT_SECONDS` to run a single command. This is usually benign (slow CI environment), but you can:

1. Increase `OOMPAH_AGENT_COMMAND_TIMEOUT_SECONDS` in `.env`:

   ```bash
   OOMPAH_AGENT_COMMAND_TIMEOUT_SECONDS=1800  # 30 minutes
   ```

2. Optimize your test suite (reduce test count, parallelize, skip slow checks for auditor runs).

### Auditor Crash (Worker Exited)

The auditor process crashed or was killed. Oompah persists the failure and
applies normal retry backoff:

1. After a restart, an in-progress attempt with no live worker is reclaimed
   immediately. An unobserved live session is reclaimed after
   `OOMPAH_AUDIT_ATTEMPT_TTL` (default 3600s).
2. Oompah rotates to the next candidate after the backoff on the next scheduler
   tick.
3. Check the orchestrator and agent logs for the crash reason (OOM, segfault, etc.).

**If crashes are frequent:**

- Increase agent memory limits (container/VM settings).
- Reduce the amount of work per audit (e.g., skip slower quality gates).
- Check provider logs for backend issues.

### Audit Queue Backing Up

If `audits_pending_count` is large and growing, audits are being queued faster than dispatched.

**Root causes:**

1. **Not enough concurrent capacity**: Increase `OOMPAH_MAX_CONCURRENT_AGENTS`.
2. **Audits taking too long**: Increase `OOMPAH_AUDIT_ATTEMPT_TTL` or optimize test commands.
3. **Provider health issues**: Inspect `GET /api/v1/providers` and test the
   affected provider through the Providers page.
4. **Budget limit reached**: Check `OOMPAH_BUDGET_LIMIT` vs. current spend.

**Remediation:**

```bash
# Check the current dispatch snapshot
curl -s http://localhost:8080/api/v1/state | jq '.orchestrator_metrics.last_dispatch'

# Update OOMPAH_MAX_CONCURRENT_AGENTS in .env, then restart for faster dispatch
make restart

# List configured providers
curl -s http://localhost:8080/api/v1/providers | jq '.[] | {id, name, mode}'
```

## Recovery

### Graceful Restart

When the lane is enabled, restarting Oompah (for example after deploying
changes) rehydrates running audits:

```bash
make restart
```

Oompah detects running attempts from metadata and:

1. Reloads each pending/in-progress audit.
2. If a live worker still owns a recent attempt, skips it; if a live worker
   exceeds `OOMPAH_AUDIT_ATTEMPT_TTL`, terminates and reclaims it.
3. If no live worker owns the attempt (the normal post-restart case), marks it
   abandoned immediately rather than launching a duplicate.
4. Rotates to the next candidate on the next scheduler tick.

This is safe and idempotent — no duplicate audits are created.

### Force Restart (Emergency)

If you need to interrupt active agents immediately (emergency):

```bash
make force-restart
```

This kills running auditors and workers without draining. They are recovered as abandoned attempts on restart.

### Stuck or abandoned audits

Do not delete `oompah.terminal_audit` metadata or move a task out of
`In Validation` by hand. The metadata is the recovery source of truth, and a
manual status change can leave the tracker and audit chain inconsistent. Use
the graceful or force restart procedure above; if the lane still cannot
recover the attempt, preserve the task identifier, audit identifier, and
service log excerpt for operator reconciliation.

## Configuration Examples

### Small Setup (Single Provider)

Auditor role:

```json
{
  "name": "auditor",
  "strategy": "priority",
  "candidates": [
    { "provider_id": "prov-main", "model": "gpt-4" }
  ]
}
```

Environment:

```bash
OOMPAH_AUDIT_MAX_ATTEMPTS=1          # Only one provider, no rotation
OOMPAH_AUDIT_ATTEMPT_TTL=1800        # 30 min (quick TTL for fast feedback)
OOMPAH_AUDIT_PRIORITY=150            # High priority to unblock tasks quickly
OOMPAH_AUDIT_LANE_SCAN_LIMIT=64      # Scan up to 64 pending audits each tick
```

### Large Setup (Multiple Providers)

Auditor role:

```json
{
  "name": "auditor",
  "strategy": "round_robin",
  "candidates": [
    { "provider_id": "prov-claude", "model": "claude-opus-4" },
    { "provider_id": "prov-openai", "model": "gpt-4-turbo" },
    { "provider_id": "prov-azure", "model": "gpt-4" },
    { "provider_id": "prov-self-hosted", "model": "llama-2-70b" }
  ]
}
```

Environment:

```bash
OOMPAH_AUDIT_MAX_ATTEMPTS=4          # Try all 4 providers before giving up
OOMPAH_AUDIT_ATTEMPT_TTL=3600        # 1 hour (allows CI to complete)
OOMPAH_AUDIT_PRIORITY=150            # Prioritize audits
OOMPAH_AUDIT_LANE_SCAN_LIMIT=32      # Batch scans to avoid GIL contention
OOMPAH_MAX_CONCURRENT_AGENTS=20      # Allow many audits + work in parallel
```

### CI/Integration Environment

Auditor role (uses internal provider only):

```json
{
  "name": "auditor",
  "strategy": "priority",
  "candidates": [
    { "provider_id": "prov-internal-api", "model": "internal-gpt-4" }
  ]
}
```

Environment:

```bash
OOMPAH_AUDIT_MAX_ATTEMPTS=3
OOMPAH_AUDIT_ATTEMPT_TTL=7200        # 2 hours (CI can be slow)
OOMPAH_AGENT_COMMAND_TIMEOUT_SECONDS=1800  # 30 min per test command
OOMPAH_BUDGET_LIMIT=0                # Unlimited (internal provider)
```

## Performance Tuning

### Reduce Audit Latency

1. **Increase priority**: `OOMPAH_AUDIT_PRIORITY=200`
2. **Increase concurrency**: set `OOMPAH_MAX_CONCURRENT_AGENTS=20` in `.env`
3. **Add more auditor candidates**: More providers = more rotation options, less queueing.

### Reduce Audit Cost

1. **Use faster models**: Configure auditor role with cheaper providers.
2. **Reduce test commands**: Disable slow quality checks in auditor sessions.
3. **Increase max attempts**: Let Oompah try all candidates before giving up (retry cost is cheap vs. manual Needs Human remediation).

### Optimize for High Throughput

1. Set `OOMPAH_AUDIT_LANE_SCAN_LIMIT=128` in `.env` (scan more audits per tick)
2. Set `OOMPAH_MAX_CONCURRENT_AGENTS=50` in `.env` (parallel audits and work)
3. Add independent providers to the auditor role (more rotation options)

## See Also

- `plans/independent-auditor-dispatch.md` — Complete design and architecture
- `docs/agent-profiles.md` — How to configure agent profiles and roles
- `docs/operator-runbook.md` — General Oompah operations guide
- `plans/terminal-transition-coordinator.md` — Audit request staging and result coordination
