---
id: OOMPAH-161
type: task
status: Archived
priority: null
title: '[backend:server] Create issue API error: Unknown project: coroot'
parent: null
children: []
blocked_by: []
labels:
- external:github
assignee: null
created_at: '2026-07-10T02:17:34.435583Z'
updated_at: '2026-07-17T03:21:18.530217Z'
work_branch: null
target_branch: null
review_url: https://github.com/lesserevil/oompah/pull/404
review_number: '404'
merged_at: null
oompah.external.github:
  id: lesserevil/oompah#403
  owner: lesserevil
  repo: oompah
  number: '403'
  url: https://github.com/lesserevil/oompah/issues/403
  requestor_login: NVShawn
  imported_comment_ids: []
  last_synced_status: Archived
  last_synced_at: '2026-07-17T03:21:17.780832+00:00'
  last_github_state: closed
oompah.intake:
  missing_fields: []
  scope: small
  requestor_approved: false
  requestor_approved_at: null
  requestor_actor: null
  owner_override: false
  owner_override_at: null
  owner_actor: null
  decomposition_status: not_needed
  proposal_fingerprint: null
  last_validator_result: pass
  last_validated_at: '2026-07-10T02:17:38.790736+00:00'
oompah.agent_run_id: 34e65c54-f9cc-400c-911c-d73ea736de88
oompah.task_costs:
  total_input_tokens: 135
  total_output_tokens: 4355
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 135
      output_tokens: 4355
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 135
    output_tokens: 4355
    cost_usd: 0.0
    recorded_at: '2026-07-10T02:42:32.732213+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/404
oompah.review_number: '404'
---
## Summary

### Problem

Oompah detected a backend error from `backend:server`:

> Create issue API error: Unknown project: coroot

### Desired Behavior

The operation in `backend:server` should complete successfully, or degrade gracefully with a clear actionable message. No unhandled error should be auto-filed as a task during normal operation.

### Steps to Reproduce

1. Run oompah with `backend:server` active.
2. Let oompah execute the operation that involves `backend:server` (tracker: `github_issues:lesserevil/oompah`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior

An error occurs in `backend:server` and is recorded by oompah's `error_watcher`:

> Create issue API error: Unknown project: coroot

### Acceptance Criteria

- The error from `backend:server` no longer occurs, or is handled gracefully so `error_watcher` is not triggered.
- The root cause is identified and resolved, or documented as a known acceptable failure with explicit handling.
- No regression: other error types continue to be reported correctly by `error_watcher`.

---
*Auto-filed by oompah error_watcher*
- source_project: global
- tracker: github_issues:lesserevil/oompah
- tracker_kind: github_issues
- fingerprint: 40762b6cac23a669
- dedup_fingerprint: 40762b6cac23a669
- tracker_owner: lesserevil
- tracker_repo: oompah

## External GitHub Issue

- URL: https://github.com/lesserevil/oompah/issues/403
- Requestor: @NVShawn
- Reference: lesserevil/oompah#403

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-10 02:34
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-10 02:34
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-10 02:34
---
Understanding: This issue reports a 'Create issue API error: Unknown project: coroot' from backend:server. My role is Duplicate Investigator. I'll search existing tasks for similar errors involving unknown projects or the 'coroot' project name before deciding whether to implement anything or archive as a duplicate.
---
author: oompah
created: 2026-07-10 02:37
---
Discovery: No duplicate found. Fingerprint 40762b6cac23a669 appears only in OOMPAH-161. No other tasks in archived/in-progress/needs-human mention 'backend:server', 'Create issue API', 'Unknown project', or 'coroot'.

Root cause: The 'coroot' project exists (id='proj-ed624f39', name='coroot') but api_create_issue in server.py calls _get_tracker(orch, project_id) where project_id='coroot' (project name). project_store.get() only looks up by internal ID ('proj-ed624f39'), not by name, so it returns None and raises ProjectError('Unknown project: coroot').

Fix: Add project-name fallback to ProjectStore.get_by_name() or have api_create_issue resolve project names to IDs before passing to _tracker_for_project. This is a new bug distinct from the webhook/trickle errors seen in other archived tasks.
---
author: oompah
created: 2026-07-10 02:41
---
Implementation: Not a duplicate — no existing task covers this error.

Changes made:
1. oompah/projects.py: Added ProjectStore.find_by_name(name) method for secondary lookup by human-readable project name.
2. oompah/orchestrator.py: Updated _tracker_for_project() to fall back to find_by_name() when the ID lookup returns None, so callers passing the project name 'coroot' instead of 'proj-ed624f39' no longer raise ProjectError. The cache is keyed by canonical ID after resolution.
3. tests/test_tracker_for_project_name_fallback.py: 7 new tests covering ID/name lookup, cache keying, error case, and the API endpoint.
4. tests/test_projects.py: 7 new tests for ProjectStore.find_by_name().
---
author: oompah
created: 2026-07-10 02:42
---
Verification: All 7249 existing tests pass plus 14 new tests:
- 7 tests for ProjectStore.find_by_name() in tests/test_projects.py
- 7 tests for _tracker_for_project name fallback and API endpoint in tests/test_tracker_for_project_name_fallback.py
No regressions.
---
author: oompah
created: 2026-07-10 02:42
---
Completion: Not a duplicate. Identified and fixed the root cause.

Root cause: api_create_issue received project_id='coroot' (the project name) but project_store.get() only looked up by internal ID ('proj-ed624f39'), returning None and raising ProjectError('Unknown project: coroot').

Fix: Added ProjectStore.find_by_name() and updated Orchestrator._tracker_for_project() to fall back to name-based lookup when ID lookup returns None. The tracker cache is keyed by canonical ID after resolution.

Branch OOMPAH-161 pushed. 14 new tests added. All 7249 tests pass.
---
author: oompah
created: 2026-07-10 02:42
---
Fixed: Added ProjectStore.find_by_name() and updated _tracker_for_project() to fall back to name lookup, resolving 'Unknown project: coroot' when project name was passed instead of internal ID. 14 new tests; all 7249 pass.
---
author: oompah
created: 2026-07-10 02:42
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 0, Tool calls: 94
- Tokens: 135 in / 4.4K out [4.5K total]
- Cost: $0.0000
- Exit: terminated, Duration: 8m 30s
- Log: OOMPAH-161__20260710T023407Z.jsonl
---
author: oompah
created: 2026-07-10 02:48
---
YOLO: merged PR #404.
---
<!-- COMMENTS:END -->
