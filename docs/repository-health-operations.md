# Repository Hygiene Health Monitoring and Operations

## Overview

Repository hygiene health monitoring helps operators distinguish between necessary retained work (active, dirty, unmerged, or audit-protected branches/worktrees) and accumulating cleanup debt (safely-prunable artifacts). Rather than targeting an unrealistic zero-branch/worktree count, green health status is based on zero overdue safely-prunable artifacts and no cleanup operation errors.

## Health Categories

Oompah categorizes worktrees and branches by their retention rationale:

### Worktree Categories

- **Active** — Currently running agent (not eligible for cleanup)
- **Dirty** — Has uncommitted changes or unpushed commits (preserve work in progress)
- **Unmerged** — Terminal state but unmerged to default branch (preserve audit trail)
- **Terminal-Protected** — Terminal and merged, kept for audit trail (operator retention)
- **Shared-Owner** — Non-project-owned worktree (external allocation, preserve)
- **Safely-Prunable** — Terminal, merged, no operational reason to retain

### Branch Categories

The same logic applies to branches:

- **Active** — Referenced by active worktree
- **Dirty** — Has unpushed commits
- **Unmerged** — Not merged to default branch
- **Terminal-Protected** — Merged but kept for audit retention
- **Shared-Owner** — Non-project-owned branch
- **Safely-Prunable** — Merged, no retention reason

## Health Status

Oompah tracks two health dimensions:

1. **Overdue Artifacts** — Safely-prunable artifacts older than the configured age threshold
2. **Cleanup Errors** — Failed cleanup operations that may indicate systemic issues

A repository is considered **healthy** when:
- Zero safely-prunable artifacts exceed the age threshold (overdue)
- Zero recent cleanup operation errors have accumulated
- All retained artifacts (active, dirty, unmerged, protected) have clear operational justification

Count thresholds are trend indicators only. They appear in the health summary
so operators can plan capacity, but do not turn a healthy repository red while
the safely-prunable artifacts remain within their age threshold.

## Configuration

Repository hygiene thresholds are configured via `.env` variables. The defaults are conservative to avoid aggressive cleanup:

```bash
# Age (seconds) before a safely-prunable artifact is overdue (default: 7 days)
OOMPAH_REPO_HYGIENE_SAFELY_PRUNABLE_AGE_SECONDS=604800

# Count threshold for warning alerts (default: 10 artifacts)
OOMPAH_REPO_HYGIENE_SAFELY_PRUNABLE_COUNT_WARNING=10

# Count threshold for critical alerts (default: 50 artifacts)
OOMPAH_REPO_HYGIENE_SAFELY_PRUNABLE_COUNT_CRITICAL=50

# Cleanup error threshold (default: 3 consecutive errors)
OOMPAH_REPO_HYGIENE_CLEANUP_ERROR_THRESHOLD=3
```

### Threshold Interpretation

- **Age Threshold**: Safely-prunable artifacts (completed work) older than this are flagged for cleanup. Increase this if temporary analysis worktrees should survive longer; decrease it for aggressive cleanup.

- **Warning Threshold**: When total safely-prunable artifacts reach this count, the dashboard adds an informational trend note so operators can plan cleanup batches. It does not raise an alert or block operations while artifacts remain within the age threshold.

- **Critical Threshold**: When total safely-prunable artifacts reach this count, the dashboard adds a critical trend note. A health alert still requires an overdue safely-prunable artifact or cleanup error.

- **Error Threshold**: Tracks cleanup operation failures. If N consecutive cleanup runs fail, an alert is raised to indicate a systemic issue (disk full, permission problem, etc.).

## Monitoring Health Status

### Dashboard

The oompah dashboard displays health status in the orchestrator metrics panel:

- **Inventory Counts** — Breakdown of worktrees and branches by category
- **Overdue Artifacts** — List of safely-prunable artifacts exceeding the age threshold
- **Cleanup Errors** — Recent cleanup operation failures (if any)
- **Health Summary** — Overall green/yellow/red status and reason

### API

Health status is exposed via the `/api/v1/snapshot` endpoint under `orchestrator_metrics.maintenance.repo_hygiene_health`:

```json
{
  "orchestrator_metrics": {
    "maintenance": {
      "repo_hygiene_health": {
        "worktrees": {
          "active": 3,
          "dirty": 2,
          "unmerged": 1,
          "terminal_protected": 5,
          "shared_owner": 0,
          "safely_prunable": 12
        },
        "branches_local": {
          "active": 3,
          "safely_prunable": 25,
          "...": "..."
        },
        "branches_remote": {
          "active": 3,
          "safely_prunable": 150,
          "...": "..."
        },
        "overdue_artifacts": [
          {
            "artifact_type": "worktree",
            "identifier": "/home/user/.oompah/workspaces/OOMPAH-100",
            "category": "safely_prunable",
            "age_seconds": 864000,
            "threshold_seconds": 604800,
            "project_id": "proj-123",
            "task_id": "OOMPAH-100"
          }
        ],
        "cleanup_errors": [],
        "is_healthy": true,
        "summary": "Repository hygiene healthy: no overdue artifacts or cleanup errors"
      }
    }
  }
}
```

## Operator Verification Procedures

### Regular Monitoring

1. **Check Dashboard Daily** — Review the health summary in the orchestrator metrics panel
2. **Monitor Alerts** — Subscribe to oompah alerts for overdue artifacts and cleanup errors
3. **Review Overdue Artifacts** — Check the list of safely-prunable artifacts that have aged beyond the threshold

### Responding to Warnings

**Warning Trend (safely-prunable count ≥ warning threshold):**
- Safe to ignore for short periods when artifacts are not overdue
- Plan a cleanup batch when convenient
- Consider increasing the warning threshold if the rate of worktree creation outpaces cleanup

**Critical Trend (safely-prunable count ≥ critical threshold):**
- Plan cleanup promptly to avoid resource exhaustion, even though health remains green until artifacts are overdue
- Check disk usage: `df -h` on the workspace root
- Review system logs for cleanup failures: `journalctl -u oompah`

**Cleanup Error Alert:**
- Immediate investigation required
- Possible causes: disk full, permission issues, filesystem corruption
- Check oompah logs: `oompah server log --follow` or `tail -f ~/.oompah/oompah.log`
- Inspect manual cleanup: ensure oompah has write access to workspace roots

### Cleanup Validation

After cleanup operations complete (either automatic or manual), validate health recovery:

```bash
# Check current health via API
curl http://localhost:8080/api/v1/snapshot | jq '.orchestrator_metrics.maintenance.repo_hygiene_health'

# Manually inspect workspace
ls -lh ~/.oompah/workspaces/ | wc -l
git -C /path/to/project branch -a | wc -l
```

Expected observations:
- `is_healthy` becomes `true`
- `overdue_artifacts` list empties
- Safely-prunable counts decrease
- Dashboard alerts clear within the next scheduler tick (default 2 minutes)

## Troubleshooting

### Cleanup Not Running

**Symptom:** Safely-prunable count grows but cleanup never runs.

**Causes:**
- Cleanup may be deferred if resource limits are active (see `deferred` flag in maintenance status)
- Cleanup scheduler may not be enabled (check `OOMPAH_WORKTREE_CLEANUP_INTERVAL_SECONDS`)
- Cleanup slices may be too strict (inspect `examined`, `cursor`, and `reason`,
  then tune `OOMPAH_WORKTREE_CLEANUP_BATCH_SIZE` or
  `OOMPAH_WORKTREE_CLEANUP_MAX_RUNTIME_SECONDS`). Skipped and failed candidates
  consume the batch budget so a large unsafe-to-prune history cannot monopolize
  the scheduler. Native Markdown trackers use strict-after bounded state pages;
  an adapter without that capability reports `unbounded_source_scan` and skips
  destructive cleanup rather than hiding an unbounded full-history read.

**Resolution:**
```bash
# Check maintenance job status
curl http://localhost:8080/api/v1/snapshot | jq '.orchestrator_metrics.maintenance.worktree_cleanup'

# Force a scheduler tick
oompah maintenance trigger --job worktree_cleanup

# Manually remove safe artifacts
git -C /path/to/project branch -D branch_name
rm -rf ~/.oompah/workspaces/OOMPAH-xxx
```

### Cleanup Errors Accumulating

**Symptom:** `cleanup_errors` list grows, health stays red.

**Causes:**
- Permission denied (oompah lost write access to workspace)
- Disk full (cleanup can't write quarantine directories)
- Stale file handles (NFS timeouts or interrupted cleanups)
- Git corruption (branches in inconsistent state)

**Resolution:**
```bash
# Check disk usage
df -h ~/.oompah/

# Verify permissions
ls -ld ~/.oompah/workspaces/
ls -ld ~/.oompah/workspaces/*/

# Check recent errors in logs
grep "cleanup" ~/.oompah/oompah.log | tail -20

# Reset a corrupted project repo
cd /path/to/project
git fsck --full
git gc --aggressive
```

### False Positives (Healthy But Trend Note)

**Symptom:** Repository appears healthy (overdue_artifacts empty) but a trend note is shown.

**Causes:**
- Safely-prunable count above threshold but all artifacts are recent
- A cleanup error was followed by a successful cleanup run

**Resolution:**
- Increase warning/critical thresholds if the artifact generation rate is expected
- Trigger a successful cleanup run; the next health evaluation clears the error

## Best Practices

1. **Set Conservative Thresholds** — Start with defaults (7 days, 10/50 counts) and increase if false positives occur
2. **Monitor Trends** — Track safely-prunable count over time; spike after deployments is normal
3. **Schedule Batch Cleanup** — If growth is steady, add cleanup to maintenance windows rather than relying on disk-pressure triggers
4. **Audit Terminal-Protected Artifacts** — Periodically review terminal-protected branches; move old ones to safely-prunable if audit trail is no longer needed
5. **Document Shared-Owner Artifacts** — If external systems own worktrees, coordinate cleanup schedules to avoid surprises

## Related Documentation

- `docs/task-epic-workflow.md` — Worktree lifecycle and branching strategy
- `docs/operator-runbook.md` — General operator maintenance procedures
- `plans/polling-mechanisms.md` — Background maintenance job scheduling
