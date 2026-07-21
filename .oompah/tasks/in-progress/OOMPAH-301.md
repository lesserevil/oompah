---
id: OOMPAH-301
type: bug
status: In Progress
priority: 2
title: '[backend:orchestrator] Fetch failed for project exocomp: State branch ''oompah/state/proj-c260b117''
  does not exist locally or at origin/''oompah/state/proj-c260b117''. Run the bootstrap
  or migration f...'
parent: null
children: []
blocked_by: []
labels:
- external:github
assignee: null
created_at: '2026-07-21T15:27:18.547293Z'
updated_at: '2026-07-21T15:46:47.176645Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.external.github:
  id: lesserevil/oompah#464
  owner: lesserevil
  repo: oompah
  number: '464'
  url: https://github.com/lesserevil/oompah/issues/464
  requestor_login: lesserevil
  imported_comment_ids: []
  last_synced_status: Backlog
  last_synced_at: '2026-07-21T15:27:30.470785+00:00'
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
  last_validated_at: '2026-07-21T15:27:23.206742+00:00'
oompah.agent_run_id: 880ffd84-7d40-4381-973f-2a9c0c1694de
oompah.task_costs:
  total_input_tokens: 368894
  total_output_tokens: 1792
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 368894
      output_tokens: 1792
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 368894
    output_tokens: 1792
    cost_usd: 0.0
    recorded_at: '2026-07-21T15:46:27.512542+00:00'
---
## Summary

### Problem

Oompah detected a backend error (error class: `tracker_failed`) from `backend:orchestrator`:

> Fetch failed for project exocomp: State branch 'oompah/state/proj-c260b117' does not exist locally or at origin/'oompah/state/proj-c260b117'. Run the bootstrap or migration flow to create it before enabling state_branch_enabled=True for this project. Normal tracker reads must not create remote branches.

### Desired Behavior

The operation in `backend:orchestrator` should complete successfully, or degrade gracefully with a clear actionable message. No unhandled error should be auto-filed as a task during normal operation.

### Steps to Reproduce

1. Run oompah with `backend:orchestrator` active.
2. Let oompah execute the operation that involves `backend:orchestrator` (tracker: `github_issues:lesserevil/oompah`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior

An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> Fetch failed for project exocomp: State branch 'oompah/state/proj-c260b117' does not exist locally or at origin/'oompah/state/proj-c260b117'. Run the bootstrap or migration flow to create it before enabling state_branch_enabled=True for this project. Normal tracker reads must not create remote branches.

### Acceptance Criteria

- The error from `backend:orchestrator` no longer occurs, or is handled gracefully so `error_watcher` is not triggered.
- The root cause is identified and resolved, or documented as a known acceptable failure with explicit handling.
- No regression: other error types continue to be reported correctly by `error_watcher`.

---
*Auto-filed by oompah error_watcher*
- source_project: global
- tracker: github_issues:lesserevil/oompah
- tracker_kind: github_issues
- fingerprint: 4dba66ecb4abddff
- dedup_fingerprint: 4dba66ecb4abddff
- tracker_owner: lesserevil
- tracker_repo: oompah
- error_class: tracker_failed

## External GitHub Issue

- URL: https://github.com/lesserevil/oompah/issues/464
- Requestor: @lesserevil
- Reference: lesserevil/oompah#464

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-21 15:45
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-21 15:45
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-21 15:46
---
Agent completed successfully in 57s (370686 tokens)
---
author: oompah
created: 2026-07-21 15:46
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 7
- Tokens: 368.9K in / 1.8K out [370.7K total]
- Cost: $0.0000
- Exit: normal, Duration: 57s
- Log: OOMPAH-301__20260721T154532Z.jsonl
---
author: oompah
created: 2026-07-21 15:46
---
Agent completed without landing — no commits found on origin for branch `OOMPAH-301`. Escalating from 'default' to 'deep'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-21 15:46
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-21 15:46
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
