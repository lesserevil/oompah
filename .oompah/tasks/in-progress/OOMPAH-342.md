---
id: OOMPAH-342
type: task
status: In Progress
priority: null
title: Wire GitLabHookManager into project lifecycle with hook health, polling fallback,
  and delivery dedup
parent: OOMPAH-325
children: []
blocked_by:
- OOMPAH-340
- OOMPAH-341
labels: []
assignee: null
created_at: '2026-07-22T00:29:14.500742Z'
updated_at: '2026-07-22T04:00:59.404479Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 30215383-0638-4e8e-aaba-7def008c15d3
---
## Summary

Integrate GitLabHookManager into the oompah project lifecycle: create hooks when GitLab projects are added, reconcile on startup, remove on deletion, track hook health, surface polling-fallback alerts, and deduplicate events delivered by both webhook and polling.

## Scope

Files to modify:
- oompah/server.py (or orchestrator.py) — project add/remove lifecycle hooks
- oompah/models.py — add hook health fields to Project
- oompah/server.py — /api/v1/webhooks/gitlab, _handle_webhook_event, alerts building
- oompah/webhooks.py — delivery dedup (or new oompah/gitlab_webhook_dedup.py)
Possibly new file: oompah/gitlab_hook_manager.py is created in OOMPAH-341

## What to implement

### Project model (oompah/models.py)
Add fields to Project:
- gitlab_hook_id: int | None = None  — ID of the installed GitLab project hook
- gitlab_hook_last_delivery_at: datetime | None = None  — UTC timestamp of last confirmed delivery
- gitlab_hook_consecutive_failures: int = 0  — count of consecutive delivery failures (missed pings or auth rejections)
- gitlab_hook_health: str = 'unknown'  — 'healthy' | 'degraded' | 'failed' | 'unknown' | 'disabled'

### Project lifecycle integration

On GitLab project creation (POST /api/v1/projects or equivalent):
- If forge_kind=='gitlab' and OOMPAH_GITLAB_WEBHOOK_PUBLIC_URL is set, call GitLabHookManager.create_hook(project) asynchronously; persist returned hook_id to project.gitlab_hook_id and set gitlab_hook_health='healthy'
- If creation fails, set gitlab_hook_health='failed' and log WARNING

On oompah startup (orchestrator tick or lifespan):
- For each project with forge_kind=='gitlab', call GitLabHookManager.reconcile_hook(project); update gitlab_hook_id if changed

On GitLab project deletion:
- If gitlab_hook_id is set, call GitLabHookManager.delete_hook(project, hook_id); swallow errors and log WARNING on failure

### Hook health tracking (in /api/v1/webhooks/gitlab handler)

On successful webhook delivery to a GitLab project:
- Set project.gitlab_hook_health = 'healthy'
- Set project.gitlab_hook_last_delivery_at = utcnow()
- Reset project.gitlab_hook_consecutive_failures = 0

On token validation failure (401):
- Increment project.gitlab_hook_consecutive_failures
- When >= 3: set gitlab_hook_health = 'degraded'
- Log WARNING (no token value)

On reconcile failure (GitLab API error):
- Set gitlab_hook_health = 'failed'

### Polling fallback alerts

Extend the alerts API (build_webhook_forwarder_alerts or equivalent) to include GitLab hook health:
- When gitlab_hook_health == 'degraded': include a warning alert recommending hook reconciliation
- When gitlab_hook_health == 'failed': include an error alert noting polling-only fallback
- When gitlab_hook_health == 'healthy': no alert

Alerts must not contain webhook_secret or gitlab_hook_id (OK to include project name and health state).

### Delivery deduplication

Add a small TTL cache (collections.OrderedDict or functools.lru_cache-based) in the webhook handler:
- Key: (project_id, event_type, content_hash) where content_hash is sha256(body_bytes)[:16]
- TTL: 30 seconds
- On duplicate: return JSON {'ok': True, 'action': 'deduplicated'} with 200 status
- On novel: process normally

The poller and webhook receiver may both deliver the same push/MR event within seconds. The dedup cache prevents double-dispatch.

## Tests to write (tests/test_gitlab_hook_lifecycle.py or additions to existing test files)

- test_gitlab_project_creation_creates_hook: POST project with forge_kind='gitlab' triggers hook creation
- test_gitlab_project_deletion_deletes_hook: DELETE project with gitlab_hook_id set calls delete_hook
- test_startup_reconciles_gitlab_hooks: orchestrator startup calls reconcile_hook for each gitlab project
- test_webhook_delivery_sets_hook_healthy: successful delivery updates health and timestamp
- test_consecutive_failures_degrade_hook_health: 3 token-validation failures set health='degraded'
- test_degraded_hook_health_appears_in_alerts: alerts include warning when health='degraded'
- test_failed_hook_health_appears_in_alerts: alerts include error when health='failed'
- test_healthy_hook_health_omits_alerts: no alert when health='healthy'
- test_duplicate_delivery_returns_deduplicated: identical body within 30s returns action='deduplicated'
- test_distinct_delivery_not_deduplicated: different body bytes not treated as duplicate
- test_alerts_do_not_contain_webhook_secret: alert text does not contain the secret value

## Dependencies
- OOMPAH-340 (webhook parser must handle all hook types) 
- OOMPAH-341 (GitLabHookManager class must exist)

## Acceptance criteria
- All new tests pass; make test passes with no regressions
- Adding a GitLab project with OOMPAH_GITLAB_WEBHOOK_PUBLIC_URL set creates a hook
- Hook health degrades on failures and recovers on successful delivery
- Polling fallback alert is visible in the dashboard/alerts API when hook is degraded/failed
- No webhook secret or token appears in alerts, logs, or API responses

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-22 03:57
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-22 03:58
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-22 04:00
---
Understanding: Investigating OOMPAH-342 as Duplicate Investigator. The issue requests wiring GitLabHookManager into the project lifecycle (hook creation on project add, reconcile on startup, remove on deletion, hook health tracking, polling-fallback alerts, event deduplication). Searching all task directories and docs for any existing task that covers the same ground before implementation work begins.
---
<!-- COMMENTS:END -->
