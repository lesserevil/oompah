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
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-22T00:29:14.500742Z'
updated_at: '2026-07-22T04:03:36.737591Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: b88f5a62-ab01-4957-840a-4a6d983769a4
oompah.task_costs:
  total_input_tokens: 49
  total_output_tokens: 9437
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 49
      output_tokens: 9437
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 33
    output_tokens: 8976
    cost_usd: 0.0
    recorded_at: '2026-07-22T04:01:42.332525+00:00'
  - profile: standard
    model: unknown
    input_tokens: 16
    output_tokens: 461
    cost_usd: 0.0
    recorded_at: '2026-07-22T04:02:45.837750+00:00'
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
author: oompah
created: 2026-07-22 04:01
---
Focus handoff: duplicate_detector

1. **Outcome**: No duplicate confirmed. OOMPAH-342 is a unique, first-of-its-kind task.

2. **Evidence searched and reviewed**:
   - All .oompah/tasks/ directories (archived 225 tasks, merged, done, in-progress, open, backlog) — no task covering this exact scope
   - Search patterns: GitLabHookManager, hook health, polling fallback, delivery dedup, project lifecycle, deduplication, gitlab hook manager
   - OOMPAH-340 (Done): Extended parse_gitlab_webhook for all hook types — a stated dependency, not a duplicate
   - OOMPAH-341 (Done): Implemented GitLabHookManager class with start()/stop(), reconcile(), remove(), and basic health tracking. Wired into server lifespan and __main__ startup/shutdown — also a dependency, NOT a duplicate. Crucially, 341 does NOT cover: (a) hook creation when a project is dynamically added via API, (b) hook removal when a project is deleted via API, (c) polling-fallback alerts when hooks are unhealthy, (d) event dedup when webhook+polling both deliver same event
   - plans/gitlab-forge-parity.md lines 81-94: documents these requirements as planned work, not an existing task

3. **Remaining work and key implementation context**:
   - **Project add hook**: `oompah/server.py` ~line 10114, after `orch.project_store.create(...)`. Call `await services.gitlab_hook_manager.reconcile()` (or per-project variant) for new GitLab projects. Pattern: see `_log_watcher_manager.sync_watchers()` calls nearby.
   - **Project delete hook**: `oompah/server.py` ~line 10519, `api_delete_project`. Call `await services.gitlab_hook_manager.remove(project)` before/after `project_store.delete()`. Already syncs log watchers same way.
   - **Project update hook**: `oompah/server.py` patch endpoint, call `reconcile()` if forge_kind/repo_url/access_token/webhook_secret changed.
   - **Hook health surfacing**: `GitLabHookManager.status` property already returns per-project health info (`healthy`, `last_error`, `hook_id`). Needs to be surfaced via project detail API or a `/api/v1/webhooks/gitlab/status` endpoint.
   - **Polling-fallback alerts**: When `state.healthy == False`, the polling-based event source should remain active and produce a dashboard alert. The `GitLabHookManager.status` `projects` dict provides the unhealthy flag per project.
   - **Event dedup**: Needs a seen-event cache (by GitLab event ID or fingerprint) shared between the webhook handler and the polling path to drop duplicate event deliveries.
   - Key files: `oompah/webhooks.py` (GitLabHookManager at line 1006), `oompah/server.py` (create ~10114, delete ~10519, update endpoint), `oompah/bootstrap.py` (services wired at lines 240, 319)

4. **Recommended next focus**: `feature` — implement the project lifecycle hooks (add/delete/update wiring) and the deduplication layer; surface hook health via API.
---
author: oompah
created: 2026-07-22 04:01
---
Agent completed successfully in 225s (9009 tokens)
---
author: oompah
created: 2026-07-22 04:01
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 65, Tool calls: 50
- Tokens: 33 in / 9.0K out [9.0K total]
- Cost: $0.0000
- Exit: normal, Duration: 3m 45s
- Log: OOMPAH-342__20260722T035800Z.jsonl
---
author: oompah
created: 2026-07-22 04:01
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-22 04:01
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-22 04:02
---
Focus: Software Engineer
---
author: oompah
created: 2026-07-22 04:02
---
Understanding: Implementing OOMPAH-342 as Software Engineer. Based on the duplicate_detector handoff, I need to implement:

1. **Project lifecycle hooks**: Call GitLabHookManager.reconcile() when GitLab projects are added/updated via API, and remove() when deleted
2. **Hook health API**: Surface GitLabHookManager.status per-project health info via a new endpoint  
3. **Polling-fallback alerts**: When hook is unhealthy, keep polling active and surface alerts
4. **Event deduplication**: Shared seen-event cache between webhook handler and polling path to drop duplicate deliveries

Key files: oompah/webhooks.py (GitLabHookManager ~line 1006), oompah/server.py (create ~10114, delete ~10519, update endpoint), oompah/bootstrap.py (services ~lines 240, 319)
---
author: oompah
created: 2026-07-22 04:02
---
Agent failed: Exception: Command failed with exit code 143 (exit code: 143)
Error output: Check stderr output for details. Retrying in 10s (attempt #1)
---
author: oompah
created: 2026-07-22 04:03
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-22 04:03
---
Focus: Software Engineer
---
<!-- COMMENTS:END -->
