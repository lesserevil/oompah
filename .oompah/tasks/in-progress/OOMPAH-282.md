---
id: OOMPAH-282
type: bug
status: In Progress
priority: 2
title: '[backend:state_branch_migration] Stage A migration failed for project proj-edbc8b4c'
parent: null
children: []
blocked_by: []
labels:
- external:github
assignee: null
created_at: '2026-07-20T22:43:02.333472Z'
updated_at: '2026-07-20T23:14:17.400818Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.external.github:
  id: lesserevil/oompah#459
  owner: lesserevil
  repo: oompah
  number: '459'
  url: https://github.com/lesserevil/oompah/issues/459
  requestor_login: lesserevil
  imported_comment_ids: []
  last_synced_status: Open
  last_synced_at: '2026-07-20T23:13:03.968818+00:00'
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
  last_validated_at: '2026-07-20T22:43:06.643323+00:00'
oompah.agent_run_id: e000df70-3f34-4882-85ef-30ef3bb5a3f9
oompah.task_costs:
  total_input_tokens: 88593
  total_output_tokens: 713
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 88593
      output_tokens: 713
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 88593
    output_tokens: 713
    cost_usd: 0.0
    recorded_at: '2026-07-20T23:09:35.637561+00:00'
---
## Summary

### Problem

Oompah detected a backend error from `backend:state_branch_migration`:

> Stage A migration failed for project proj-edbc8b4c

**Error detail:**

```
Stage A migration failed for project proj-edbc8b4c

Traceback (most recent call last):
  File "/home/shedwards/src/oompah/oompah/state_branch_migration.py", line 434, in migrate_stage_a
    result = initialize_state_branch(
             ^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/shedwards/src/oompah/oompah/project_bootstrap/__init__.py", line 380, in initialize_state_branch
    tar_bytes = archive_r.stdout.encode("latin-1") if isinstance(archive_r.stdout, str) else archive_r.stdout
                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
UnicodeEncodeError: 'latin-1' codec can't encode character '\u2014' in position 26154: ordinal not in range(256)

```

### Desired Behavior

The operation in `backend:state_branch_migration` should complete successfully, or degrade gracefully with a clear actionable message. No unhandled error should be auto-filed as a task during normal operation.

### Steps to Reproduce

1. Run oompah with `backend:state_branch_migration` active.
2. Let oompah execute the operation that involves `backend:state_branch_migration` (tracker: `github_issues:lesserevil/oompah`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior

An error occurs in `backend:state_branch_migration` and is recorded by oompah's `error_watcher`:

> Stage A migration failed for project proj-edbc8b4c

### Acceptance Criteria

- The error from `backend:state_branch_migration` no longer occurs, or is handled gracefully so `error_watcher` is not triggered.
- The root cause is identified and resolved, or documented as a known acceptable failure with explicit handling.
- No regression: other error types continue to be reported correctly by `error_watcher`.

---
*Auto-filed by oompah error_watcher*
- source_project: global
- tracker: github_issues:lesserevil/oompah
- tracker_kind: github_issues
- fingerprint: 9eaadc366ca8cc18
- dedup_fingerprint: 9eaadc366ca8cc18
- tracker_owner: lesserevil
- tracker_repo: oompah

## External GitHub Issue

- URL: https://github.com/lesserevil/oompah/issues/459
- Requestor: @lesserevil
- Reference: lesserevil/oompah#459

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-20 23:09
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-20 23:09
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-20 23:09
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 0
- Tokens: 88.6K in / 713 out [89.3K total]
- Cost: $0.0000
- Exit: normal, Duration: 25s
- Log: OOMPAH-282__20260720T230913Z.jsonl
---
author: oompah
created: 2026-07-20 23:09
---
Agent completed successfully in 25s (89306 tokens)
---
author: oompah
created: 2026-07-20 23:09
---
Agent completed without landing — no commits found on origin for branch `OOMPAH-282`. Escalating from 'default' to 'deep'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-20 23:10
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-20 23:10
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-20 23:14
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-20 23:14
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
