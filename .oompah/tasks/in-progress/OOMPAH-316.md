---
id: OOMPAH-316
type: bug
status: In Progress
priority: 2
title: '[backend:server] Fetch issues failed for project exocomp: State branch ''oompah/state/proj-c260b117''
  does not exist locally or at origin/''oompah/state/proj-c260b117''. Run the bootstrap
  or migration ...'
parent: null
children: []
blocked_by: []
labels:
- external:github
assignee: null
created_at: '2026-07-21T18:20:20.146747Z'
updated_at: '2026-07-21T18:51:27.335682Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.external.github:
  id: lesserevil/oompah#471
  owner: lesserevil
  repo: oompah
  number: '471'
  url: https://github.com/lesserevil/oompah/issues/471
  requestor_login: lesserevil
  imported_comment_ids: []
  last_synced_status: In Progress
  last_synced_at: '2026-07-21T18:50:34.864937+00:00'
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
  last_validated_at: '2026-07-21T18:20:35.323844+00:00'
oompah.agent_run_id: 1671179f-97cc-4988-a063-0be15b19b0f6
oompah.task_costs:
  total_input_tokens: 175055
  total_output_tokens: 1362
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 175055
      output_tokens: 1362
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 175055
    output_tokens: 1362
    cost_usd: 0.0
    recorded_at: '2026-07-21T18:50:53.962647+00:00'
---
## Summary

### Problem

Oompah detected a backend error from `backend:server`:

> Fetch issues failed for project exocomp: State branch 'oompah/state/proj-c260b117' does not exist locally or at origin/'oompah/state/proj-c260b117'. Run the bootstrap or migration flow to create it before enabling state_branch_enabled=True for this project. Normal tracker reads must not create remote branches.

### Desired Behavior

The operation in `backend:server` should complete successfully, or degrade gracefully with a clear actionable message. No unhandled error should be auto-filed as a task during normal operation.

### Steps to Reproduce

1. Run oompah with `backend:server` active.
2. Let oompah execute the operation that involves `backend:server` (tracker: `github_issues:lesserevil/oompah`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior

An error occurs in `backend:server` and is recorded by oompah's `error_watcher`:

> Fetch issues failed for project exocomp: State branch 'oompah/state/proj-c260b117' does not exist locally or at origin/'oompah/state/proj-c260b117'. Run the bootstrap or migration flow to create it before enabling state_branch_enabled=True for this project. Normal tracker reads must not create remote branches.

### Acceptance Criteria

- The error from `backend:server` no longer occurs, or is handled gracefully so `error_watcher` is not triggered.
- The root cause is identified and resolved, or documented as a known acceptable failure with explicit handling.
- No regression: other error types continue to be reported correctly by `error_watcher`.

---
*Auto-filed by oompah error_watcher*
- source_project: global
- tracker: github_issues:lesserevil/oompah
- tracker_kind: github_issues
- fingerprint: 9a803f3b8b56abc0
- dedup_fingerprint: 9a803f3b8b56abc0
- tracker_owner: lesserevil
- tracker_repo: oompah

## External GitHub Issue

- URL: https://github.com/lesserevil/oompah/issues/471
- Requestor: @lesserevil
- Reference: lesserevil/oompah#471

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-21 18:50
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-21 18:50
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-21 18:50
---
Agent completed successfully in 50s (176417 tokens)
---
author: oompah
created: 2026-07-21 18:50
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 3
- Tokens: 175.1K in / 1.4K out [176.4K total]
- Cost: $0.0000
- Exit: normal, Duration: 50s
- Log: OOMPAH-316__20260721T185006Z.jsonl
---
author: oompah
created: 2026-07-21 18:50
---
Agent completed without landing — no commits found on origin for branch `OOMPAH-316`. Escalating from 'default' to 'deep'. Retrying in 10s (1/3).
---
<!-- COMMENTS:END -->
