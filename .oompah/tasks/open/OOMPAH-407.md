---
id: OOMPAH-407
type: bug
status: Open
priority: 2
title: '[backend:orchestrator] Dispatch loop stale: no tick completed in 900s (threshold=900s).
  Alert armed, recovery queued.'
parent: null
children: []
blocked_by: []
labels:
- external:github
assignee: null
created_at: '2026-07-22T08:36:37.862938Z'
updated_at: '2026-07-22T15:40:04.686832Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.external.github:
  id: lesserevil/oompah#536
  owner: lesserevil
  repo: oompah
  number: '536'
  url: https://github.com/lesserevil/oompah/issues/536
  requestor_login: NVShawn
  imported_comment_ids: []
  last_synced_status: Open
  last_synced_at: '2026-07-22T15:40:03.984461+00:00'
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
  last_validated_at: '2026-07-22T08:37:55.309711+00:00'
oompah.agent_run_id: 6e991ed1-29c5-4153-9fe6-87e986f42174
oompah.task_costs:
  total_input_tokens: 698487
  total_output_tokens: 3925
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 698487
      output_tokens: 3925
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 346127
    output_tokens: 1989
    cost_usd: 0.0
    recorded_at: '2026-07-22T15:35:22.708899+00:00'
  - profile: deep
    model: unknown
    input_tokens: 352360
    output_tokens: 1936
    cost_usd: 0.0
    recorded_at: '2026-07-22T15:36:37.494411+00:00'
---
## Summary

### Problem

Oompah detected a backend error from `backend:orchestrator`:

> Dispatch loop stale: no tick completed in 900s (threshold=900s). Alert armed, recovery queued.

### Desired Behavior

The operation in `backend:orchestrator` should complete successfully, or degrade gracefully with a clear actionable message. No unhandled error should be auto-filed as a task during normal operation.

### Steps to Reproduce

1. Run oompah with `backend:orchestrator` active.
2. Let oompah execute the operation that involves `backend:orchestrator` (tracker: `github_issues:lesserevil/oompah`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior

An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> Dispatch loop stale: no tick completed in 900s (threshold=900s). Alert armed, recovery queued.

### Acceptance Criteria

- The error from `backend:orchestrator` no longer occurs, or is handled gracefully so `error_watcher` is not triggered.
- The root cause is identified and resolved, or documented as a known acceptable failure with explicit handling.
- No regression: other error types continue to be reported correctly by `error_watcher`.

---
*Auto-filed by oompah error_watcher*
- source_project: global
- tracker: github_issues:lesserevil/oompah
- tracker_kind: github_issues
- fingerprint: 636fd17c490ee7f4
- dedup_fingerprint: 636fd17c490ee7f4
- tracker_owner: lesserevil
- tracker_repo: oompah

## External GitHub Issue

- URL: https://github.com/lesserevil/oompah/issues/536
- Requestor: @NVShawn
- Reference: lesserevil/oompah#536

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-22 15:34
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-22 15:34
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-22 15:35
---
Agent completed successfully in 54s (348116 tokens)
---
author: oompah
created: 2026-07-22 15:35
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 7
- Tokens: 346.1K in / 2.0K out [348.1K total]
- Cost: $0.0000
- Exit: normal, Duration: 54s
- Log: OOMPAH-407__20260722T153431Z.jsonl
---
author: oompah
created: 2026-07-22 15:35
---
Agent completed without landing — no commits found on origin for branch `OOMPAH-407`. Escalating from 'default' to 'deep'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-22 15:35
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-22 15:35
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-22 15:36
---
Agent completed successfully in 53s (354296 tokens)
---
author: oompah
created: 2026-07-22 15:36
---
Run #2 [attempt=2, profile=deep, role=deep -> Codex/default]
- Turns: 1, Tool calls: 6
- Tokens: 352.4K in / 1.9K out [354.3K total]
- Cost: $0.0000
- Exit: normal, Duration: 53s
- Log: OOMPAH-407__20260722T153546Z.jsonl
---
author: oompah
created: 2026-07-22 15:36
---
Agent completed without landing — no commits found on origin for branch `OOMPAH-407`. No stronger profile is configured; retrying with 'deep' in 20s (2/3).
---
author: oompah
created: 2026-07-22 15:37
---
Retrying (attempt #2, agent: deep)
---
author: oompah
created: 2026-07-22 15:37
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
