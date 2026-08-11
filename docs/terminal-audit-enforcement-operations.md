# Terminal-Audit Enforcement: Operator Guide

**Audience:** Operators managing oompah deployments
**Related:** `plans/terminal-audit-enforcement.md` (design), `plans/terminal-transition-coordinator.md` (coordinator)

## Overview

Terminal-audit enforcement is a periodic reconciliation pass that runs at server startup. It detects tasks that have become terminal (Done, Merged, Archived) without going through the coordinator and queues them for audit.

**Key guarantees**:

- No task can silently reach a terminal state without audit
- "Grandfathered" pre-existing terminal tasks are trusted on first startup
- Changed evidence (new code, updated requirements) triggers re-audit even if state is unchanged
- All state is durable; restart recovery is idempotent

## Quick Start

Terminal-audit enforcement runs automatically on server startup. **No operator configuration is required** for basic operation.

### Verify Enforcement is Active

After server startup, check the logs:

```bash
grep -i "terminal-audit enforcement" oompah.log
```

Expected output:

```
INFO: Terminal-audit enforcement initialized: {'first_startup': True, 'baseline_initialized': True, 'quarantined': False, 'grandfathered': 42, 'pending_audits': 0, 'errors': []}
```

**Interpretation**:

| Field | Meaning |
|-------|---------|
| `first_startup: True` | First run; baseline was just created |
| `baseline_initialized: True` | Baseline was accepted; will be used for future comparisons |
| `quarantined: False` | No errors; baseline is trustworthy |
| `grandfathered: 42` | 42 pre-existing terminal tasks are in the baseline |
| `pending_audits: 0` | No new/changed tasks need audit |
| `errors: []` | No errors encountered |

### Check Service State

The enforcement baseline is stored in `service_state.json` (default: `workspace/service_state.json`):

```bash
jq '.terminal_audit_enforcement' workspace/service_state.json | head -50
```

Expected structure:

```json
{
  "version": 1,
  "baseline_initialized": true,
  "grandfathered": [
    {
      "project_id": "proj-abc",
      "task_id": "TASK-123",
      "terminal_state": "Done",
      "evidence_fingerprint": {
        "digest": "abc123def456..."
      }
    }
  ],
  "invalidated": [],
  "pending_audits": [],
  "quarantined": false,
  "errors": []
}
```

## Scenarios

### Scenario 1: First Startup (Creating Baseline)

**What happens**:

1. Server starts and runs enforcement
2. All existing terminal tasks are scanned
3. For each task, evidence fingerprint is computed and stored
4. Baseline is written to `service_state.json`
5. No audits are queued (we assume existing tasks are safe)

**Expected log**:

```
INFO: Terminal-audit enforcement initialized: {
  'first_startup': True,
  'baseline_initialized': True,
  'quarantined': False,
  'grandfathered': 47,
  'pending_audits': 0,
  'errors': []
}
```

**Operator action**: None required. Baseline is ready for future enforcement.

### Scenario 2: Detecting Changed Evidence

**What happens**:

1. A task in the baseline changes its requirements (e.g., new feature added)
2. Evidence fingerprint changes (different source SHA or requirements text)
3. On next startup, enforcement detects the fingerprint mismatch
4. Task is moved to "invalidated" list and queued for audit
5. Auditor picks it up and re-audits with new evidence

**Expected log**:

```
INFO: Terminal-audit enforcement initialized: {
  'first_startup': False,
  'baseline_initialized': True,
  'quarantined': False,
  'grandfathered': 46,
  'pending_audits': 1,
  'errors': []
}
```

**Operator action**: Monitor audit results. If audit passes, baseline is automatically updated.

### Scenario 3: Detecting Direct Tracker Mutations

**What happens**:

1. A task is manually marked as Done in GitHub/GitLab (bypassing the coordinator)
2. Or a label change directly triggers a terminal-state update
3. On next startup, enforcement finds the task was not terminal before (not in baseline)
4. Task is queued for immediate audit

**Example flow**:

```bash
# Before: TASK-100 is in "Open" status
$ curl get/TASK-100 | jq '.state'
"Open"

# Manual mutation: operator marks task as Done in tracker UI
# or: $ gh issue edit OOMPAH-100 --state closed

# After: TASK-100 is "Done", but enforcement has no record of the request

# Next server restart:
$ grep "TASK-100" workspace/service_state.json
# Not in grandfathered list

$ grep "pending_audits" workspace/service_state.json
# TASK-100 is now queued for audit
```

**Expected log**:

```
INFO: Terminal-audit enforcement initialized: {
  'first_startup': False,
  'baseline_initialized': True,
  'quarantined': False,
  'grandfathered': 46,
  'pending_audits': 1,
  'errors': []
}

INFO: TASK-100 queued for terminal-state audit (enforcement)
```

**Operator action**: This is intentional. The audit will verify the task meets termination criteria. If it passes, enforcement updates the baseline. If it fails, the task is routed to a repair status.

### Scenario 4: Corrupt Service State

**What happens**:

1. `service_state.json` is corrupted (e.g., invalid JSON, version mismatch)
2. Enforcement cannot parse the baseline
3. Quarantine mode is activated
4. **All observed terminal tasks** are queued for audit (fail-closed)

**Expected log**:

```
ERROR: terminal-audit enforcement: service_state_corrupt (json.JSONDecodeError)
ERROR: terminal-audit enforcement: terminal_audit_enforcement_corrupt (ValueError)

INFO: Terminal-audit enforcement initialized: {
  'first_startup': False,
  'baseline_initialized': False,
  'quarantined': True,
  'grandfathered': 0,
  'pending_audits': 47,
  'errors': ['service_state_corrupt', 'terminal_audit_enforcement_corrupt']
}
```

**Operator action**:

1. **Inspect the error**: Check logs for the specific failure
2. **Fix or reset**: Either repair `service_state.json` or delete it (baseline will be recreated on next startup)
3. **Review queued audits**: 47 tasks are now queued for audit; monitor their progress
4. **Verify baseline on next startup**: Once `service_state.json` is healthy, `quarantined` should return to `false`

**Recovery**:

```bash
# Option 1: Repair the file (if only a small issue)
jq . workspace/service_state.json > /tmp/fixed.json && \
  mv /tmp/fixed.json workspace/service_state.json

# Option 2: Reset the baseline (enforces re-audit of all current terminal tasks)
rm workspace/service_state.json
make restart
```

### Scenario 5: Metadata Corruption (In Validation Task)

**What happens**:

1. A task is in "In Validation" status (audit in progress)
2. Its metadata is corrupted (malformed JSON or missing fields)
3. Enforcement cannot parse the pending audit record
4. The entry is quarantined and logged, but enforcement continues

**Expected log**:

```
ERROR: terminal-audit enforcement: metadata_quarantined:proj-abc:TASK-50
ERROR: terminal-audit enforcement: metadata_read_failed:proj-abc:TASK-50

INFO: Terminal-audit enforcement initialized: {
  'first_startup': False,
  'baseline_initialized': True,
  'quarantined': True,
  'grandfathered': 46,
  'pending_audits': 0,
  'errors': ['metadata_quarantined:proj-abc:TASK-50']
}
```

**Operator action**:

1. **Identify the problematic task**: `TASK-50` has corrupted metadata
2. **Inspect through the managed task API and server logs**:
   ```bash
   oompah task view TASK-50 --project proj-abc
   ```
3. **Do not delete or hand-edit terminal-audit metadata.** Result intents,
   owner overrides, and status-departure markers form one validated ledger.
   Recovery fails closed before modifying any row when that ledger is
   malformed.
4. **Repair the source through an owner-authorized tracker operation**, then
   restart with `make restart`. If the ledger itself requires repair, stop the
   server and use the project-specific recovery procedure rather than editing
   a live task.

Relevant fail-closed error prefixes include
`pre_recovery_finalization_metadata_malformed`,
`validation_status_departure_records_malformed`,
`inactive_status_departure_records_malformed`, and
`status_departure_recovery_failed`. The suffix identifies the project and
task.

### Scenario 6: Restart Recovery

**What happens**:

1. Server crashes while an audit is in progress (status `IN_PROGRESS`)
2. Enforcement validates the complete result, override, and status-departure
   ledger before applying recovery mutations
3. An audit that still has exact `In Validation` authority is re-enqueued with
   its existing generation and attempt identity
4. An audit whose task left `In Validation` is retired; its incompatible
   runtime job and attempt worktree are cleaned up, with cleanup retried on a
   later reconciliation if the first attempt fails
5. If an interrupted status transition returns the task to `In Validation`
   with the same immutable evidence, the durable departure marker creates a
   fresh audit generation and fresh identifiers. The cancelled generation is
   never revived
6. If immutable evidence is temporarily unavailable, recovery keeps the
   departure marker unapplied and retries instead of guessing

**Expected log**:

```
INFO: Terminal-audit enforcement initialized: {
  'first_startup': False,
  'baseline_initialized': True,
  'quarantined': False,
  'grandfathered': 46,
  'pending_audits': 1,
  'errors': []
}

INFO: Recovered 1 pending audit from In Validation metadata
```

**Operator action**: None required for a valid ledger. The auditor resumes an
exact in-flight generation or receives the fresh generation created by
status-departure recovery. Investigate only persistent fail-closed errors;
do not clear a transient marker or cleanup retry manually.

## Monitoring and Alerting

### Key Metrics

Monitor these values in `service_state.json`:

```json
{
  "terminal_audit_enforcement": {
    "baseline_initialized": true,     // FALSE = baseline not ready
    "quarantined": false,             // TRUE = errors detected
    "grandfathered": 47,              // Count of trusted baseline entries
    "pending_audits": 2,              // Count waiting to be audited
    "errors": []                      // Error codes (non-empty = investigate)
  }
}
```

### Alerting Rules

**Alert if**:

| Condition | Severity | Action |
|-----------|----------|--------|
| `quarantined: true` after startup | P1 | Operator must inspect logs and fix `service_state.json` |
| `pending_audits > 50` after 1 hour | P2 | Auditor may be slow; check auditor logs and queue status |
| `"errors"` array is non-empty | P1 | Operator must review error codes and fix root cause |
| `baseline_initialized: false` after 2 startups | P1 | Indicates persistent scan or parse failure; escalate |

### Log Patterns to Watch

**Healthy**:

```
INFO: Terminal-audit enforcement initialized: {..., 'quarantined': False, 'errors': []}
```

**Investigate**:

```
ERROR: terminal-audit enforcement: service_state_corrupt
ERROR: terminal-audit enforcement: task_scan_failed:proj-xyz
ERROR: terminal-audit enforcement: evidence_fingerprint_failed:proj-xyz:TASK-123
ERROR: terminal-audit enforcement: metadata_quarantined:proj-xyz:TASK-456
```

**Use grep to find errors**:

```bash
grep "ERROR: terminal-audit enforcement" oompah.log | sort | uniq -c
```

## Manual Operations

### Force Baseline Reset

If the baseline is stale or incorrect, reset it:

```bash
rm workspace/service_state.json
make restart
```

This will:

1. Delete the old baseline
2. Restart the server
3. Re-run enforcement with fresh scan
4. Create a new baseline from current state
5. Queue any changed/new terminal tasks for audit

### Manually Promote a Task to Baseline

After an audit passes, enforcement automatically promotes the task into the baseline via `mark_audit_passed()`. If you need to manually do this (e.g., for an exempted task):

```python
# Internal operation (not exposed via CLI yet)
# Documented here for future feature requests

enforcer = TerminalAuditEnforcement(state_path="workspace/service_state.json")
enforcer.mark_audit_passed(
    project_id="proj-abc",
    issue=task,
    fingerprint=computed_fingerprint,
)
# Task is now in grandfathered baseline
```

### Quarantine Recovery Checklist

If `quarantined: true`:

1. [ ] Check logs for error codes:
   ```bash
   grep ERROR oompah.log | grep terminal-audit | head -20
   ```

2. [ ] If `service_state_corrupt`:
   ```bash
   jq . workspace/service_state.json  # Validate JSON
   ```

3. [ ] If `task_scan_failed`:
   ```bash
   # Check tracker connectivity and permissions
   # Verify tracker adapters are working
   ```

4. [ ] If `metadata_quarantined`:
   ```bash
   # Find the task with bad metadata
   grep metadata_quarantined oompah.log | grep -oP '(?<=:)\w+-\d+'
   # Manually review that task's In Validation metadata
   ```

5. [ ] After fixing issues, restart:
   ```bash
   make restart
   ```

6. [ ] Verify quarantine is cleared:
   ```bash
   jq '.terminal_audit_enforcement.quarantined' workspace/service_state.json
   # Should be false
   ```

## Configuration

Terminal-audit enforcement runs automatically with default settings. Configuration is rarely needed.

### Configured Terminal States

By default, terminal states are `["Done", "Merged", "Archived"]`. If your tracker uses custom states, configure them in `WORKFLOW.md`:

```yaml
# WORKFLOW.md
...
terminal_states:
  - "Done"
  - "Merged"
  - "Archived"
  - "Resolved"  # Custom state
```

The enforcement passes this list during initialization.

### Service State Path

The baseline is stored at the path configured in the orchestrator (default: `workspace/service_state.json`). To use a different path:

```bash
# Set environment variable (if supported by your deployment)
export OOMPAH_STATE_PATH="/data/persistent/oompah-state.json"
make start
```

## Troubleshooting

### "Pending Audits Never Decrease"

**Symptom**: `pending_audits` count stays constant or grows, never decreases.

**Cause**: Auditor is not consuming the queue.

**Check**:

```bash
# 1. Verify auditor is running
ps aux | grep auditor

# 2. Check auditor logs for errors
grep -i auditor oompah.log | grep -i error | head -10

# 3. Check if tasks are stuck in In Validation
gh issue list --state all --label "In Validation" | wc -l
```

**Fix**:

- Restart auditor: `make restart`
- Check auditor permissions: Can it read/write to tracker?
- Verify network connectivity to tracker (GitHub API rate limits, etc.)

### "Evidence Fingerprint Changed Unexpectedly"

**Symptom**: Tasks are being re-audited even though nothing changed.

**Cause**: Evidence fingerprint is non-deterministic or includes unstable data.

**Check**:

```python
# Manually compute fingerprint twice
from oompah.terminal_audit import EvidenceFingerprint

fp1 = EvidenceFingerprint.from_evidence(
    requirements_text="text",
    project_id="proj",
    task_id="TASK-1",
)

fp2 = EvidenceFingerprint.from_evidence(
    requirements_text="text",
    project_id="proj",
    task_id="TASK-1",
)

assert fp1 == fp2  # Should be equal
```

**Solutions**:

- Ensure issue metadata is stable (requirements text, SHAs, contributors don't change spuriously)
- Avoid including timestamps or randomized data in fingerprint inputs
- Check tracker adapter — it should compute fingerprint consistently

### "Baseline Shows Wrong Project_id"

**Symptom**: Baseline has entries with incorrect project_id.

**Cause**: Tracker adapter is not providing `project_id` correctly.

**Check**:

```bash
# View baseline entries
jq '.terminal_audit_enforcement.grandfathered[0] | {project_id, task_id}' workspace/service_state.json
```

**Fix**:

```bash
# Reset baseline if wrong project_ids
rm workspace/service_state.json
make restart
```

Ensure tracker adapter correctly populates `issue.project_id`.

## Glossary

| Term | Definition |
|------|-----------|
| **Grandfathered** | A task in the baseline; trusted; does not require re-audit unless evidence changes |
| **Invalidated** | A task that was in the baseline but its evidence or state changed; queued for re-audit |
| **Evidence Fingerprint** | SHA-256 digest of task requirements, source/target SHAs, review state, contributors; stable across identical inputs |
| **Baseline** | Set of grandfathered terminal tasks; snapshots on first startup; used for comparison in later runs |
| **Quarantined** | Enforcement entered error mode; baseline not updated; all observed terminal tasks queued |
| **In Validation** | Task status while audit is pending or in progress; task metadata contains audit chain |
| **Audit Chain** | Durable sequence of `TerminalAuditRecord` entries (PENDING, IN_PROGRESS, COMPLETED, SUPERSEDED); stored in task metadata |

## See Also

- `plans/terminal-audit-enforcement.md` — Design and implementation details
- `plans/terminal-transition-coordinator.md` — Coordinator staging system
- `docs/task-epic-workflow.md` — Terminal states and task lifecycle
- `tests/test_terminal_audit_enforcement.py` — Test coverage and examples
