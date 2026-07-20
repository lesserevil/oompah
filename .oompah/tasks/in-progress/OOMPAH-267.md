---
id: OOMPAH-267
type: bug
status: In Progress
priority: 2
title: "[backend:server] Add comment API error: git commit -m Comment on oompah task\
  \ OOMPAH-266\n\n\U0001F916 Generated with https://github.com/lesserevil/oompah\n\
  \nCo-authored-by: oompah <lesserevil@users.noreply.gith..."
parent: null
children: []
blocked_by: []
labels:
- external:github
assignee: null
created_at: '2026-07-20T16:51:11.086624Z'
updated_at: '2026-07-20T16:58:31.148333Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.external.github:
  id: lesserevil/oompah#453
  owner: lesserevil
  repo: oompah
  number: '453'
  url: https://github.com/lesserevil/oompah/issues/453
  requestor_login: NVShawn
  imported_comment_ids: []
  last_synced_status: In Progress
  last_synced_at: '2026-07-20T16:58:27.140462+00:00'
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
  last_validated_at: '2026-07-20T16:51:30.711929+00:00'
oompah.agent_run_id: f930f126-7cd3-4164-a36a-49c44039074e
oompah.task_costs:
  total_input_tokens: 9
  total_output_tokens: 3
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 9
      output_tokens: 3
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 9
    output_tokens: 3
    cost_usd: 0.0
    recorded_at: '2026-07-20T16:56:38.298001+00:00'
---
## Summary

### Problem

Oompah detected a backend error from `backend:server`:

> Add comment API error: git commit -m Comment on oompah task OOMPAH-266

🤖 Generated with https://github.com/lesserevil/oompah

Co-authored-by: oompah <lesserevil@users.noreply.github.com>
 failed: fatal: cannot lock ref 'HEAD': is at df6135ea58c6e6bdac8de56169bce64f2ca953c8 but expected 46558c30aa2ea303df139557c48067ceee30bc53

### Desired Behavior

The operation in `backend:server` should complete successfully, or degrade gracefully with a clear actionable message. No unhandled error should be auto-filed as a task during normal operation.

### Steps to Reproduce

1. Run oompah with `backend:server` active.
2. Let oompah execute the operation that involves `backend:server` (tracker: `github_issues:lesserevil/oompah`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior

An error occurs in `backend:server` and is recorded by oompah's `error_watcher`:

> Add comment API error: git commit -m Comment on oompah task OOMPAH-266

🤖 Generated with https://github.com/lesserevil/oompah

Co-authored-by: oompah <lesserevil@users.noreply.github.com>
 failed: fatal: cannot lock ref 'HEAD': is at df6135ea58c6e6bdac8de56169bce64f2ca953c8 but expected 46558c30aa2ea303df139557c48067ceee30bc53

### Acceptance Criteria

- The error from `backend:server` no longer occurs, or is handled gracefully so `error_watcher` is not triggered.
- The root cause is identified and resolved, or documented as a known acceptable failure with explicit handling.
- No regression: other error types continue to be reported correctly by `error_watcher`.

---
*Auto-filed by oompah error_watcher*
- source_project: global
- tracker: github_issues:lesserevil/oompah
- tracker_kind: github_issues
- fingerprint: ec0c2cce6c7d7177
- dedup_fingerprint: ec0c2cce6c7d7177
- tracker_owner: lesserevil
- tracker_repo: oompah

## External GitHub Issue

- URL: https://github.com/lesserevil/oompah/issues/453
- Requestor: @NVShawn
- Reference: lesserevil/oompah#453

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-20 16:55
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-20 16:55
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-20 16:56
---
Understanding: This issue reports a git ref locking error when oompah tries to commit a comment on task OOMPAH-266. The error 'fatal: cannot lock ref HEAD: is at X but expected Y' indicates a concurrent git commit race condition — two git operations attempted to commit simultaneously and one lost the race. My role is to determine if this is a duplicate of a previously-handled issue before any implementation work begins.
---
author: oompah
created: 2026-07-20 16:56
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 0, Tool calls: 1
- Tokens: 9 in / 3 out [12 total]
- Cost: $0.0000
- Exit: terminated, Duration: 58s
- Log: OOMPAH-267__20260720T165601Z.jsonl
---
author: oompah
created: 2026-07-20 16:57
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-20 16:57
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
