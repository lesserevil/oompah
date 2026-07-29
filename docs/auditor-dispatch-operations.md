# Independent Auditor Dispatch — Operations Guide

This guide is for operators running Oompah with independent auditor dispatch enabled. It covers configuration, monitoring, troubleshooting, and recovery for the audit queue system.

**See also:** `plans/independent-auditor-dispatch.md` (design and architecture)

## Overview

When a task completes and moves toward a terminal state (Done, Merged, Archived), Oompah stages an audit request and moves the task to the `In Validation` state. The independent auditor dispatch lane:

1. Reads queued audit requests from tasks in `In Validation`
2. Selects an independent auditor (provider/model not used by the task's contributors)
3. Launches a reserved auditor agent with read-only verification tools
4. Handles retry and rotation if the auditor's provider is unavailable or busy
5. Routes exhausted audits (no remaining candidates) to `Needs Human` with configuration guidance

## Configuration

### Environment Variables

Add these to your `.env` file to tune the auditor dispatch system:

#### Core Auditor Settings

```bash
# Maximum number of auditor candidates to attempt per audit before
# routing to Needs Human when all independent candidates fail.
# Recommended: 3-5 (gives each candidate a fair chance at retrying).
# Set to 0 to disable audit dispatch entirely (for testing only).
OOMPAH_AUDIT_MAX_ATTEMPTS=3

# Time-to-live (seconds) for running auditor attempts.
# If an auditor session crashes or hangs and remains in "in-progress"
# for longer than this, it is considered abandoned and eligible for retry.
# Recommended: 3600 (1 hour). Set higher for slower CI environments.
OOMPAH_AUDIT_ATTEMPT_TTL=3600

# Relative priority for dispatching In Validation audits vs. Open issues.
# Higher priority means audits are dispatched sooner. Recommended: 100-200.
# Set to 0 to deprioritize audits (ordinary work first).
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
OOMPAH_BUDGET_LIMIT=100.00

# Retry backoff settings (same for audits and normal work).
# Maximum delay between retries; audits with multiple candidates
# rotate immediately (no backoff), but subsequent full rotations use this.
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

**Strategy:**
- **`priority`**: Use candidates in configured order; rotate only on failure.
- **`round_robin`**: Cycle through candidates by last-used timestamp to spread load.

**Adding candidates:**

1. Via dashboard: Navigate to the Roles section and edit the auditor role.
2. Via CLI: Edit `.oompah/roles.json` directly (and restart Oompah).
3. Via API: `PUT /api/v1/roles/auditor` with the updated candidate list.

**Provider independence check:**

Before each audit, Oompah verifies that the selected auditor provider is independent from the task's contributors:

- If contributors used `prov-fast/gpt-4o`, then `prov-fast/gpt-4o` is skipped.
- If contributors used `prov-standard` with unknown model (ACP SDK-managed), then all `prov-standard` candidates are skipped (fail-closed).
- If only dependent candidates remain, the audit is routed to `Needs Human` with a `no_independent_auditor` reason.

## Monitoring

### Dashboard

The Oompah dashboard displays:

- **In Validation tasks**: count and list under the "In Validation" column.
- **Running audits**: active auditor agents shown in the "Active Agents" section.
- **Audit metrics**: dispatch lane statistics in the metrics sidebar.

### Logs

Watch the orchestrator logs for audit dispatch activity:

```bash
# Tail logs in real-time
tail -f ~/.oompah/logs/orchestrator.log | grep -i audit

# Example output:
# [INFO] audit dispatch: starting audit-1 (task OOMPAH-123) on prov-fast/gpt-4, candidate rotation 0
# [INFO] audit dispatch: auditor exit (audit-1) — transient failure, rotating to next candidate
# [INFO] audit dispatch: rotation failed — no independent candidates; routing to Needs Human
```

### Metrics Endpoints

Check current audit queue depth and auditor agent counts:

```bash
# Get metrics snapshot
curl -s http://localhost:8080/api/v1/metrics | jq '.audits'

# Example response:
{
  "audits_pending_count": 3,
  "audits_in_progress_count": 2,
  "audit_dispatch_count_total": 45,
  "audit_exhaustion_count_total": 1,
  "audit_attempt_duration_ms_histogram": {
    "p50": 30000,
    "p95": 120000,
    "p99": 300000
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

The selected provider returned a rate-limit error. Oompah automatically rotates to the next candidate.

**If rotations keep failing:**

1. Check provider health: Dashboard → Providers → check rate-limit status.
2. Increase the provider's quota or throttle limit in the provider configuration.
3. Add more independent providers to the auditor role.
4. Increase `OOMPAH_AUDIT_ATTEMPT_TTL` if the audit is spending too long waiting for rate-limit recovery.

### Auditor Timeout (Took Too Long)

The auditor took longer than `OOMPAH_AGENT_COMMAND_TIMEOUT_SECONDS` to run a single command. This is usually benign (slow CI environment), but you can:

1. Increase `OOMPAH_AGENT_COMMAND_TIMEOUT_SECONDS` in `.env`:

   ```bash
   OOMPAH_AGENT_COMMAND_TIMEOUT_SECONDS=1800  # 30 minutes
   ```

2. Optimize your test suite (reduce test count, parallelize, skip slow checks for auditor runs).

### Auditor Crash (Worker Exited)

The auditor process crashed or was killed. Oompah detects this on the next scheduler tick:

1. Check `OOMPAH_AUDIT_ATTEMPT_TTL` (default 3600s). If the attempt is older than this, it is marked abandoned.
2. Oompah rotates to the next candidate on the next scheduler tick.
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
3. **Provider health issues**: Check `curl http://localhost:8080/api/v1/providers` for health status.
4. **Budget limit reached**: Check `OOMPAH_BUDGET_LIMIT` vs. current spend.

**Remediation:**

```bash
# Check queue depth
curl -s http://localhost:8080/api/v1/metrics | jq '.audits_pending_count'

# Increase concurrency for faster dispatch
export OOMPAH_MAX_CONCURRENT_AGENTS=10
make restart

# Check provider health
curl -s http://localhost:8080/api/v1/providers | jq '.[] | {name, health}'
```

## Recovery

### Graceful Restart

When you restart Oompah (e.g., after deploying changes), running audits are recovered:

```bash
make restart
```

Oompah detects running attempts from metadata and:

1. Reloads each pending/in-progress audit.
2. If the attempt is older than `OOMPAH_AUDIT_ATTEMPT_TTL`, marks it abandoned.
3. Rotates to the next candidate on the next scheduler tick.
4. If the attempt is recent, assumes the auditor is still running and skips.

This is safe and idempotent — no duplicate audits are created.

### Force Restart (Emergency)

If you need to interrupt active agents immediately (emergency):

```bash
make force-restart
```

This kills running auditors and workers without draining. They are recovered as abandoned attempts on restart.

### Manually Skip a Stuck Audit

If an audit is stuck and you need to unblock the task:

```bash
# Re-open the task (moves it out of In Validation)
oompah task set-status OOMPAH-123 Open

# Then manually trigger work dispatch
# (or wait for the next scheduler tick)
```

This leaves the audit incomplete, but allows normal work to resume on the task.

### Clear the Audit Queue (Testing Only)

To reset all pending/in-progress audits (for testing), you must edit task metadata directly:

```bash
# This is dangerous and should only be done for testing.
# Back up .oompah/tasks before editing.

# Remove oompah.terminal_audit from task metadata:
rg -l 'oompah.terminal_audit' .oompah/tasks | xargs sed -i '/"oompah\.terminal_audit"/d'

# Then restart Oompah
make restart
```

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
OOMPAH_AUDIT_LANE_SCAN_LIMIT=64      # Scan all pending audits each tick
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
2. **Increase concurrency**: `OOMPAH_MAX_CONCURRENT_AGENTS=20`
3. **Add more auditor candidates**: More providers = more rotation options, less queueing.

### Reduce Audit Cost

1. **Use faster models**: Configure auditor role with cheaper providers.
2. **Reduce test commands**: Disable slow quality checks in auditor sessions.
3. **Increase max attempts**: Let Oompah try all candidates before giving up (retry cost is cheap vs. manual Needs Human remediation).

### Optimize for High Throughput

1. `OOMPAH_AUDIT_LANE_SCAN_LIMIT=128` (scan more audits per tick)
2. `OOMPAH_MAX_CONCURRENT_AGENTS=50` (parallel audits)
3. Round-robin role strategy (spread load across candidates)

## See Also

- `plans/independent-auditor-dispatch.md` — Complete design and architecture
- `docs/agent-profiles.md` — How to configure agent profiles and roles
- `docs/operator-runbook.md` — General Oompah operations guide
- `plans/terminal-transition-coordinator.md` — Audit request staging and result coordination
