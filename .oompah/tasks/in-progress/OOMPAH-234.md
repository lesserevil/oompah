---
id: OOMPAH-234
type: bug
status: In Progress
priority: 2
title: '[backend:webhooks] WebhookForwarder: disabling webhook forwarding for project
  trickle: configured repo_path is missing or not a directory'
parent: null
children: []
blocked_by: []
labels:
- external:github
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-18T12:01:21.441371Z'
updated_at: '2026-07-18T12:10:24.709802Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.external.github:
  id: lesserevil/oompah#440
  owner: lesserevil
  repo: oompah
  number: '440'
  url: https://github.com/lesserevil/oompah/issues/440
  requestor_login: lesserevil
  imported_comment_ids: []
  last_synced_status: In Progress
  last_synced_at: '2026-07-18T12:08:12.779555+00:00'
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
  last_validated_at: '2026-07-18T12:01:46.647532+00:00'
oompah.agent_run_id: c43dcb37-84fd-4b26-b1f4-d4af9b4ec3a5
oompah.task_costs:
  total_input_tokens: 13
  total_output_tokens: 4419
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 13
      output_tokens: 4419
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 13
    output_tokens: 4419
    cost_usd: 0.0
    recorded_at: '2026-07-18T12:09:57.776261+00:00'
---
## Summary

### Problem

Oompah detected a backend error from `backend:webhooks`:

> WebhookForwarder: disabling webhook forwarding for project trickle: configured repo_path is missing or not a directory

### Desired Behavior

The operation in `backend:webhooks` should complete successfully, or degrade gracefully with a clear actionable message. No unhandled error should be auto-filed as a task during normal operation.

### Steps to Reproduce

1. Run oompah with `backend:webhooks` active.
2. Let oompah execute the operation that involves `backend:webhooks` (tracker: `github_issues:lesserevil/oompah`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior

An error occurs in `backend:webhooks` and is recorded by oompah's `error_watcher`:

> WebhookForwarder: disabling webhook forwarding for project trickle: configured repo_path is missing or not a directory

### Acceptance Criteria

- The error from `backend:webhooks` no longer occurs, or is handled gracefully so `error_watcher` is not triggered.
- The root cause is identified and resolved, or documented as a known acceptable failure with explicit handling.
- No regression: other error types continue to be reported correctly by `error_watcher`.

---
*Auto-filed by oompah error_watcher*
- source_project: global
- tracker: github_issues:lesserevil/oompah
- tracker_kind: github_issues
- fingerprint: 622aaaa5848fc5b4
- dedup_fingerprint: 622aaaa5848fc5b4
- tracker_owner: lesserevil
- tracker_repo: oompah

## External GitHub Issue

- URL: https://github.com/lesserevil/oompah/issues/440
- Requestor: @lesserevil
- Reference: lesserevil/oompah#440

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-18 12:07
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-18 12:07
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-18 12:08
---
Understanding: Investigating whether this issue is a duplicate. The error 'WebhookForwarder: disabling webhook forwarding for project trickle: configured repo_path is missing or not a directory' was auto-filed by error_watcher. My role is to search for existing tasks covering the same root cause before any implementation begins.
---
author: oompah
created: 2026-07-18 12:09
---
Focus handoff: duplicate_detector

**Outcome:** No duplicate confirmed. This is a unique issue.

**Evidence reviewed:**
- Searched .oompah/tasks for 'repo_path is missing or not a directory' — only appears in OOMPAH-234 itself.
- The fingerprint `622aaaa5848fc5b4` is unique to OOMPAH-234.
- Many archived tasks (OOMPAH-62, OOMPAH-82, OOMPAH-113, OOMPAH-118, OOMPAH-125, etc.) have similar titles '[backend:webhooks] WebhookForwarder: disabling webhook forwarding for project trickle' but carry a different error: 'gh: Not Found (HTTP 404)'. These are a different root cause (GitHub API 404) handled in a different code path.
- OOMPAH-188 (Merged) has error 'gh: Resource not accessible by personal access token (HTTP 403)' — again a different root cause.

**Root cause location:** `oompah/webhooks.py` around line 1246–1258. When `_try_launch_project()` is called, it checks `if not repo_path or not os.path.isdir(repo_path)` and calls `_record_project_error(..., fatal=True)` which logs at ERROR level (triggering error_watcher). The 'trickle' project has a `repo_path` configured that either doesn't exist or isn't a directory on this host.

**Remaining work:**
- Determine why the 'trickle' project's repo_path is invalid (path missing, wrong config, or project shouldn't have webhook forwarding enabled).
- Fix: either correct the repo_path config for 'trickle', or downgrade the log from ERROR to WARNING/DEBUG for the repo_path-missing case (since it's a configuration issue, not a runtime failure), so error_watcher doesn't auto-file tasks for it.
- The code at line 1249 already has a `logger.debug(...)` for the same condition — but the subsequent `_record_project_error(..., fatal=True)` emits `logger.error(...)` which triggers error_watcher.

**Recommended next focus:** `bug` (backend fix — either config correction or log-level adjustment in webhooks.py)
---
author: oompah
created: 2026-07-18 12:09
---
Agent completed successfully in 121s (4432 tokens)
---
author: oompah
created: 2026-07-18 12:10
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 35, Tool calls: 17
- Tokens: 13 in / 4.4K out [4.4K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 1s
- Log: OOMPAH-234__20260718T120803Z.jsonl
---
author: oompah
created: 2026-07-18 12:10
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-18 12:10
---
Agent dispatched (profile: default)
---
<!-- COMMENTS:END -->
