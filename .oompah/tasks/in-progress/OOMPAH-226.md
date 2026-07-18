---
id: OOMPAH-226
type: bug
status: In Progress
priority: 2
title: '[backend:oompah_md_tracker] Duplicate native oompah task ID trickle-39 at
  /home/shedwards/.oompah/repos/trickle/.oompah/tasks/done/TRICKLE-39.md and /home/shedwards/.oompah/repos/trickle/.oompah/ta...'
parent: null
children: []
blocked_by: []
labels:
- external:github
assignee: null
created_at: '2026-07-18T01:07:33.012372Z'
updated_at: '2026-07-18T02:02:39.953160Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.external.github:
  id: lesserevil/oompah#431
  owner: lesserevil
  repo: oompah
  number: '431'
  url: https://github.com/lesserevil/oompah/issues/431
  requestor_login: NVShawn
  imported_comment_ids: []
  last_synced_status: Open
  last_synced_at: '2026-07-18T01:47:03.362021+00:00'
oompah.intake:
  missing_fields: []
  scope: unknown
  requestor_approved: false
  requestor_approved_at: null
  requestor_actor: null
  owner_override: false
  owner_override_at: null
  owner_actor: null
  decomposition_status: not_needed
  proposal_fingerprint: null
  last_validator_result: pass
  last_validated_at: '2026-07-18T01:09:00.028835+00:00'
oompah.agent_run_id: 5009f102-7e81-42fb-aaf6-cc372d375153
oompah.task_costs:
  total_input_tokens: 132207
  total_output_tokens: 1038
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 132207
      output_tokens: 1038
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 132207
    output_tokens: 1038
    cost_usd: 0.0
    recorded_at: '2026-07-18T02:02:04.351317+00:00'
---
## Summary

### Problem

Oompah detected a backend error from `backend:oompah_md_tracker`:

> Duplicate native oompah task ID trickle-39 at /home/shedwards/.oompah/repos/trickle/.oompah/tasks/done/TRICKLE-39.md and /home/shedwards/.oompah/repos/trickle/.oompah/tasks/merged/TRICKLE-39.md; using /home/shedwards/.oompah/repos/trickle/.oompah/tasks/merged/TRICKLE-39.md and ignoring /home/shedwards/.oompah/repos/trickle/.oompah/tasks/done/TRICKLE-39.md. Repair the stale record before editing this task.

### Desired Behavior

The operation in `backend:oompah_md_tracker` should complete successfully, or degrade gracefully with a clear actionable message. No unhandled error should be auto-filed as a task during normal operation.

### Steps to Reproduce

1. Run oompah with `backend:oompah_md_tracker` active.
2. Let oompah execute the operation that involves `backend:oompah_md_tracker` (tracker: `github_issues:lesserevil/oompah`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior

An error occurs in `backend:oompah_md_tracker` and is recorded by oompah's `error_watcher`:

> Duplicate native oompah task ID trickle-39 at /home/shedwards/.oompah/repos/trickle/.oompah/tasks/done/TRICKLE-39.md and /home/shedwards/.oompah/repos/trickle/.oompah/tasks/merged/TRICKLE-39.md; using /home/shedwards/.oompah/repos/trickle/.oompah/tasks/merged/TRICKLE-39.md and ignoring /home/shedwards/.oompah/repos/trickle/.oompah/tasks/done/TRICKLE-39.md. Repair the stale record before editing this task.

### Acceptance Criteria

- The error from `backend:oompah_md_tracker` no longer occurs, or is handled gracefully so `error_watcher` is not triggered.
- The root cause is identified and resolved, or documented as a known acceptable failure with explicit handling.
- No regression: other error types continue to be reported correctly by `error_watcher`.

---
*Auto-filed by oompah error_watcher*
- source_project: global
- tracker: github_issues:lesserevil/oompah
- tracker_kind: github_issues
- fingerprint: 856f3622858ff901
- dedup_fingerprint: 856f3622858ff901
- tracker_owner: lesserevil
- tracker_repo: oompah

## External GitHub Issue

- URL: https://github.com/lesserevil/oompah/issues/431
- Requestor: @NVShawn
- Reference: lesserevil/oompah#431

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-18 02:01
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-18 02:01
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-18 02:02
---
Agent completed successfully in 43s (133245 tokens)
---
author: oompah
created: 2026-07-18 02:02
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 2
- Tokens: 132.2K in / 1.0K out [133.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 43s
- Log: OOMPAH-226__20260718T020138Z.jsonl
---
author: oompah
created: 2026-07-18 02:02
---
Agent completed without landing — no commits found on origin for branch `OOMPAH-226`. Escalating from 'default' to 'deep'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-18 02:02
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-18 02:02
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
